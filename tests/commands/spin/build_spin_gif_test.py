import unittest

import discord

from ironforgedbot.commands.spin.build_spin_gif import (
    FRAME_COUNT,
    GIF_HEIGHT,
    GIF_WIDTH,
    ITEM_HEIGHT,
    _ease_out_cubic,
    _get_text_alpha,
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


class TestBuildSpinFrames(unittest.TestCase):
    def test_frame_count(self):
        options = ["red", "blue", "green"]
        frames = build_spin_frames(options, 0)
        self.assertEqual(len(frames), FRAME_COUNT)

    def test_frame_size_and_mode(self):
        options = ["red", "blue", "green"]
        frames = build_spin_frames(options, 0)
        for frame in frames:
            self.assertEqual(frame.mode, "RGBA")
            self.assertEqual(frame.size, (GIF_WIDTH, GIF_HEIGHT))


class TestBuildSpinGifFile(unittest.IsolatedAsyncioTestCase):
    async def test_returns_discord_file(self):
        options = ["red", "blue", "green"]
        file, _ = await build_spin_gif_file(options)
        self.assertIsInstance(file, discord.File)

    async def test_gif_magic_bytes(self):
        options = ["red", "blue", "green"]
        file, _ = await build_spin_gif_file(options)
        magic = file.fp.read(6)
        self.assertEqual(magic, b"\x47\x49\x46\x38\x39\x61")  # GIF89a signature

    async def test_file_size_reasonable(self):
        options = ["red", "blue", "green"]
        file, _ = await build_spin_gif_file(options)
        file.fp.seek(0)
        data = file.fp.read()
        self.assertGreater(len(data), 1024)  # > 1 KB
        self.assertLess(len(data), 3 * 1024 * 1024)  # < 3 MB

    async def test_winner_is_valid_option(self):
        options = ["red", "blue", "green", "yellow"]
        _, winner = await build_spin_gif_file(options)
        self.assertIn(winner, options)
