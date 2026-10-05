import asyncio
import threading
import time
import unittest
from unittest.mock import patch

import discord
from PIL import Image, ImageChops, ImageDraw, ImageFont

from ironforgedbot.commands.spin.build_spin_gif import (
    CONFETTI_FRAMES,
    FADEOUT_FRAMES,
    FRAME_COUNT,
    FRAME_DURATION_MS,
    GIF_HEIGHT,
    GIF_WIDTH,
    FONT_PATH,
    ITEM_HEIGHT,
    OUTRO_FRAMES,
    SPIN_FRAMES,
    _TextMasks,
    _create_text_masks,
    _draw_text_with_masks,
    _ease_out_cubic,
    _ensure_opaque_background,
    _get_text_alpha,
    _consume_frames_to_rgb,
    build_spin_frames,
    build_spin_gif_file,
)


class TestEaseOutCubic(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(_ease_out_cubic(0.0), 0.0)

    def test_one(self):
        self.assertEqual(_ease_out_cubic(1.0), 1.0)

    def test_half_greater_than_half(self):
        # ease-out starts fast, so at t=0.5 the eased value should be > 0.5
        self.assertGreater(_ease_out_cubic(0.5), 0.5)


class TestGetTextAlpha(unittest.TestCase):
    def test_center_fully_opaque(self):
        self.assertEqual(_get_text_alpha(0, ITEM_HEIGHT), 255)

    def test_far_item_invisible(self):
        self.assertEqual(_get_text_alpha(ITEM_HEIGHT * 2, ITEM_HEIGHT), 0)

    def test_partial_alpha(self):
        alpha = _get_text_alpha(ITEM_HEIGHT, ITEM_HEIGHT)
        self.assertGreater(alpha, 0)
        self.assertLess(alpha, 255)


class TestTextMasks(unittest.TestCase):
    def test_draws_fill_and_outline(self):
        image = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        font = ImageFont.truetype(FONT_PATH, size=40)
        masks = _create_text_masks("Winner", font)

        self.assertIsInstance(masks, _TextMasks)
        _draw_text_with_masks(ImageDraw.Draw(image), 20, 20, masks, 255)

        colors = {color for _, color in image.getcolors(image.width * image.height)}
        self.assertIn((255, 255, 0, 255), colors)
        self.assertIn((0, 0, 0, 255), colors)

    def test_cached_masks_match_stroked_text(self):
        font = ImageFont.truetype(FONT_PATH, size=40)
        text = "Winning Option"
        masks = _create_text_masks(text, font)
        for alpha in (1, 64, 128, 200, 255):
            for y in (20.0, 20.5, 20.9):
                native_image = Image.new("RGBA", (500, 200), (0, 0, 0, 0))
                cached_image = Image.new("RGBA", (500, 200), (0, 0, 0, 0))

                ImageDraw.Draw(native_image).text(
                    (100, y),
                    text,
                    font=font,
                    fill=(255, 255, 0, alpha),
                    stroke_width=2,
                    stroke_fill=(0, 0, 0, alpha),
                )
                _draw_text_with_masks(
                    ImageDraw.Draw(cached_image), 100, y, masks, alpha
                )

                self.assertIsNone(
                    ImageChops.difference(native_image, cached_image)
                    .convert("RGB")
                    .getbbox()
                )


class TestEnsureOpaqueBackground(unittest.TestCase):
    def test_preserves_opaque_background(self):
        background = Image.new("RGBA", (1, 1), (10, 20, 30, 255))

        result = _ensure_opaque_background(background)

        self.assertIs(result, background)

    def test_flattens_transparent_background_to_gif_matte(self):
        background = Image.new("RGBA", (1, 1), (10, 20, 30, 0))

        result = _ensure_opaque_background(background)

        self.assertEqual(result.getpixel((0, 0)), (43, 45, 49, 255))


class TestBuildSpinFrames(unittest.TestCase):
    def test_balanced_phase_frame_counts(self):
        self.assertEqual(
            (SPIN_FRAMES, FADEOUT_FRAMES, CONFETTI_FRAMES, OUTRO_FRAMES),
            (90, 15, 45, 15),
        )
        self.assertEqual(FRAME_COUNT, 165)

    def test_frame_count_size_and_mode(self):
        options = ["red", "blue", "green"]
        frames = build_spin_frames(options, 0)
        try:
            self.assertEqual(len(frames), FRAME_COUNT)
            phase_boundary = ImageChops.difference(
                frames[SPIN_FRAMES - 1], frames[SPIN_FRAMES]
            )
            self.assertIsNone(phase_boundary.convert("RGB").getbbox())
            for frame in frames:
                self.assertEqual(frame.mode, "RGBA")
                self.assertEqual(frame.size, (GIF_WIDTH, GIF_HEIGHT))
        finally:
            for frame in frames:
                frame.close()


class TestConsumeFramesToRgb(unittest.TestCase):
    def test_converts_frames_and_closes_rgba_sources(self):
        frame = Image.new("RGBA", (1, 1), (10, 20, 30, 255))
        frames = [frame]

        with patch.object(frame, "close", wraps=frame.close) as close:
            result = _consume_frames_to_rgb(frames)

        self.assertEqual(result[0].mode, "RGB")
        self.assertEqual(result[0].getpixel((0, 0)), (10, 20, 30))
        close.assert_called_once_with()
        self.assertEqual(frames, [])
        result[0].close()


class TestBuildSpinGifFile(unittest.IsolatedAsyncioTestCase):
    async def test_generated_gif_meets_output_contract(self):
        options = ["red", "blue", "green"]
        file, winner = await build_spin_gif_file(options)

        try:
            self.assertIsInstance(file, discord.File)
            self.assertIn(winner, options)
            self.assertGreater(file.fp.getbuffer().nbytes, 1024)
            self.assertLess(file.fp.getbuffer().nbytes, 5 * 1024 * 1024)
            self.assertEqual(file.fp.getvalue()[:6], b"\x47\x49\x46\x38\x39\x61")

            with Image.open(file.fp) as gif:
                self.assertEqual(gif.size, (GIF_WIDTH, GIF_HEIGHT))
                self.assertEqual(gif.info["duration"], FRAME_DURATION_MS)
                durations = []
                for index in range(gif.n_frames):
                    gif.seek(index)
                    durations.append(gif.info["duration"])
                self.assertEqual(sum(durations), FRAME_COUNT * FRAME_DURATION_MS)
        finally:
            file.close()

    async def test_empty_options_raise_clear_error(self):
        with self.assertRaisesRegex(ValueError, "At least one option"):
            await build_spin_gif_file([])

    async def test_generation_is_limited_to_one_worker(self):
        lock = threading.Lock()
        active_generations = 0
        max_active_generations = 0

        def slow_build(options):
            nonlocal active_generations, max_active_generations
            with lock:
                active_generations += 1
                max_active_generations = max(max_active_generations, active_generations)
            time.sleep(0.02)
            with lock:
                active_generations -= 1
            return None, options[0]

        with patch(
            "ironforgedbot.commands.spin.build_spin_gif._build_spin_gif_sync",
            side_effect=slow_build,
        ):
            await asyncio.gather(
                build_spin_gif_file(["red"]),
                build_spin_gif_file(["blue"]),
                build_spin_gif_file(["green"]),
            )

        self.assertEqual(max_active_generations, 1)
