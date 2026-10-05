import asyncio
import io
import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import discord
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

GIF_WIDTH, GIF_HEIGHT = 500, 200
FRAME_DURATION_MS = 70  # GIF delays use 10 ms increments; ~14.3 fps
GIF_BACKGROUND_COLOR = (43, 45, 49, 255)
TEXT_OUTLINE_COLOR = (0, 0, 0)
TEXT_FILL_COLOR = (255, 255, 0)
TEXT_OUTLINE_WIDTH = 2
_GIF_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gif-generation")
FIXED_SCROLL_ITEMS = (
    50  # fixed item count scrolled before landing, keeps speed consistent
)
FONT_SIZE = 40  # Large enough to read clearly at 500px width
ITEM_HEIGHT = 50  # Provides comfortable vertical spacing between text items

SPIN_FRAMES = 90  # ~6.3 seconds of spinning at 14.3fps
FADEOUT_FRAMES = 15  # ~1.05 seconds for non-winners to fade out
CONFETTI_FRAMES = 45  # ~3.15 seconds of confetti celebration
FADEIN_FRAMES = 15  # first N spin frames where all text fades in (0 -> 1)
OUTRO_FRAMES = 15  # ~1.05 seconds fade to background for clean loop point

FRAME_COUNT = SPIN_FRAMES + FADEOUT_FRAMES + CONFETTI_FRAMES + OUTRO_FRAMES

CONFETTI_COUNT = 80  # Dense confetti without overwhelming the winner text
CONFETTI_SIZE = 6  # Large enough to be visible, small enough to look like confetti
CONFETTI_COLORS = [
    (220, 50, 50),  # red
    (50, 100, 220),  # blue
    (50, 180, 50),  # green
    (240, 210, 50),  # yellow
    (200, 50, 200),  # magenta
    (50, 200, 200),  # cyan
    (240, 130, 30),  # orange
    (230, 230, 230),  # white
]

MAX_GIF_SIZE = 25 * 1024 * 1024  # 25 MB

BACKGROUND_IMAGE_PATH = "data/img/spin_background.png"
FONT_PATH = "data/fonts/runescape.ttf"


def _ease_out_cubic(t: float) -> float:
    """Cubic ease-out curve: fast at the start, decelerates to a stop at t=1."""
    return 1 - (1 - t) ** 3


def _get_text_alpha(distance: float, item_height: int) -> int:
    """Return 0-255 alpha based on distance from centre slot.

    Items within 1.5 slot-heights of centre are fully visible; beyond that they
    fade linearly to transparent, creating a depth-of-field illusion.
    """
    alpha = max(0.0, 1.0 - distance / (item_height * 1.5))
    return int(alpha * 255)


def _ensure_opaque_background(background: Image.Image) -> Image.Image:
    """Flatten transparent pixels once so every generated frame is opaque."""
    if background.getchannel("A").getextrema() == (255, 255):
        return background

    matte = Image.new("RGBA", background.size, GIF_BACKGROUND_COLOR)
    return Image.alpha_composite(matte, background)


def _load_background() -> Image.Image:
    """Load and resize the background image to GIF dimensions.

    Uses context manager to ensure file handle is closed immediately.
    Falls back to solid color if image file is missing.
    """
    try:
        with Image.open(BACKGROUND_IMAGE_PATH) as img:
            # Convert and resize while file is open, returns new image
            return img.convert("RGBA").resize((GIF_WIDTH, GIF_HEIGHT))
    except FileNotFoundError:
        return Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (20, 20, 40, 255))


@dataclass(frozen=True)
class _TextMasks:
    """Cached outline and fill masks, including glyph origin offsets."""

    outline: Image.Image
    fill: Image.Image
    left: int
    top: int


@dataclass(frozen=True)
class _TextLayout:
    """Centered text geometry and pre-rendered masks for one option."""

    top: int
    height: int
    center_x: int
    masks: _TextMasks


@dataclass(frozen=True)
class _ConfettiParticle:
    """Initial position, velocity, and color for one confetti particle."""

    start_x: int
    start_y: float
    velocity_x: float
    velocity_y: float
    color: tuple[int, int, int]


def _create_text_masks(
    text: str,
    font: ImageFont.FreeTypeFont,
    outline_width: int = TEXT_OUTLINE_WIDTH,
) -> _TextMasks:
    """Rasterize text fill and outline once for reuse across animation frames."""
    left, top, right, bottom = font.getbbox(text, stroke_width=outline_width)
    size = (right - left, bottom - top)

    outline = Image.new("L", size, 0)
    fill = Image.new("L", size, 0)
    ImageDraw.Draw(outline).text(
        (-left, -top),
        text,
        font=font,
        fill=255,
        stroke_width=outline_width,
        stroke_fill=255,
    )
    ImageDraw.Draw(fill).text((-left, -top), text, font=font, fill=255)

    return _TextMasks(outline, fill, left, top)


def _draw_text_with_masks(
    draw: ImageDraw.Draw,
    x: float,
    y: float,
    masks: _TextMasks,
    alpha: int,
) -> None:
    """Composite cached text masks at requested position and opacity."""
    position = (round(x) + masks.left, round(y) + masks.top)
    draw.bitmap(position, masks.outline, fill=(*TEXT_OUTLINE_COLOR, alpha))
    draw.bitmap(position, masks.fill, fill=(*TEXT_FILL_COLOR, alpha))


class _SpinFrameRenderer:
    """Render each animation phase using shared background and text assets."""

    def __init__(self, options: list[str], selected_index: int) -> None:
        self.options = options
        self.selected_index = selected_index
        self.total_scroll_items = (
            math.ceil(FIXED_SCROLL_ITEMS / len(options)) * len(options) + selected_index
        )
        self.total_scroll_px = self.total_scroll_items * ITEM_HEIGHT
        self.center_y = GIF_HEIGHT / 2
        self.font = ImageFont.truetype(FONT_PATH, size=FONT_SIZE)
        self.background = _ensure_opaque_background(_load_background())
        self.text_layouts = self._build_text_layouts()

    def _build_text_layouts(self) -> dict[str, _TextLayout]:
        layouts: dict[str, _TextLayout] = {}
        for text in set(self.options):
            left, top, right, bottom = self.font.getbbox(text)
            layouts[text] = _TextLayout(
                top=top,
                height=bottom - top,
                center_x=(GIF_WIDTH - (right - left)) // 2,
                masks=_create_text_masks(text, self.font),
            )
        return layouts

    def _new_overlay(self) -> tuple[Image.Image, ImageDraw.Draw]:
        overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        return overlay, ImageDraw.Draw(overlay)

    def _draw_option(
        self, draw: ImageDraw.Draw, text: str, center_y: float, alpha: int
    ) -> None:
        if alpha == 0:
            return

        layout = self.text_layouts[text]
        text_y = center_y - layout.height / 2 - layout.top
        _draw_text_with_masks(draw, layout.center_x, text_y, layout.masks, alpha)

    def render(self) -> list[Image.Image]:
        frames = self._render_spin_phase()
        frames.extend(self._render_fadeout_phase())
        frames.extend(self._render_celebration_phase())
        return frames

    def _render_spin_phase(self) -> list[Image.Image]:
        frames: list[Image.Image] = []
        for i in range(SPIN_FRAMES):
            progress = i / (SPIN_FRAMES - 1)
            scroll = self.total_scroll_px * _ease_out_cubic(progress)

            # Hold exact landing position in final frames to prevent jitter.
            if i >= SPIN_FRAMES - 5:
                scroll = self.total_scroll_px

            scroll_items = scroll / ITEM_HEIGHT
            base_index = int(scroll_items)
            fraction = scroll_items - base_index
            # Avoid a one-pixel flicker at near-integer slot boundaries.
            if fraction > 1 - 1e-3:
                fraction = 0.0
                base_index += 1

            fadein_alpha = min(1.0, i / (FADEIN_FRAMES - 1))
            overlay, draw = self._new_overlay()

            for offset in range(-3, 4):
                item_y = self.center_y + (offset - fraction) * ITEM_HEIGHT
                item_index = (base_index + offset) % len(self.options)
                text = self.options[item_index]
                alpha = _get_text_alpha(abs(item_y - self.center_y), ITEM_HEIGHT)
                self._draw_option(draw, text, item_y, int(alpha * fadein_alpha))

            frames.append(Image.alpha_composite(self.background, overlay))

        return frames

    def _render_fadeout_phase(self) -> list[Image.Image]:
        frames: list[Image.Image] = []
        for frame_index in range(FADEOUT_FRAMES):
            progress = frame_index / (FADEOUT_FRAMES - 1)
            overlay, draw = self._new_overlay()

            for offset in range(-3, 4):
                item_y = self.center_y + offset * ITEM_HEIGHT
                item_index = (self.total_scroll_items + offset) % len(self.options)
                text = self.options[item_index]

                if item_index == self.selected_index:
                    alpha = 255
                else:
                    base_alpha = _get_text_alpha(
                        abs(item_y - self.center_y), ITEM_HEIGHT
                    )
                    alpha = int(base_alpha * (1.0 - progress))

                self._draw_option(draw, text, item_y, alpha)

            frames.append(Image.alpha_composite(self.background, overlay))

        return frames

    def _create_confetti_particles(
        self,
    ) -> list[_ConfettiParticle]:
        # Keep confetti layout repeatable for a given selected option index.
        rng = random.Random(self.selected_index)
        return [
            _ConfettiParticle(
                start_x=rng.randint(0, GIF_WIDTH - CONFETTI_SIZE),
                start_y=rng.uniform(-GIF_HEIGHT, 0),
                velocity_x=rng.uniform(-2.0, 2.0),
                velocity_y=rng.uniform(3.0, 6.0),
                color=rng.choice(CONFETTI_COLORS),
            )
            for _ in range(CONFETTI_COUNT)
        ]

    def _render_celebration_phase(self) -> list[Image.Image]:
        frames: list[Image.Image] = []
        winner_text = self.options[self.selected_index]
        particles = self._create_confetti_particles()

        # Use continuous frame indices so confetti motion stays smooth at outro.
        for frame_index in range(CONFETTI_FRAMES + OUTRO_FRAMES):
            outro_index = frame_index - CONFETTI_FRAMES
            fade = 1.0 if outro_index < 0 else 1.0 - outro_index / (OUTRO_FRAMES - 1)
            alpha = int(255 * fade)

            text_overlay, text_draw = self._new_overlay()
            self._draw_option(text_draw, winner_text, self.center_y, alpha)

            confetti_overlay, confetti_draw = self._new_overlay()
            for particle in particles:
                x = int(
                    (particle.start_x + particle.velocity_x * frame_index) % GIF_WIDTH
                )
                y = int(particle.start_y + particle.velocity_y * frame_index)
                if 0 <= y < GIF_HEIGHT:
                    confetti_draw.rectangle(
                        [
                            x,
                            y,
                            x + CONFETTI_SIZE - 1,
                            y + CONFETTI_SIZE - 1,
                        ],
                        fill=(*particle.color, alpha),
                    )

            composite = Image.alpha_composite(self.background, text_overlay)
            frames.append(Image.alpha_composite(composite, confetti_overlay))

        return frames


def build_spin_frames(options: list[str], selected_index: int) -> list[Image.Image]:
    """Build all animation frames across spin, fade, and celebration phases."""
    _validate_options(options)
    if not 0 <= selected_index < len(options):
        raise ValueError("selected_index must identify an option")
    return _SpinFrameRenderer(options, selected_index).render()


def _validate_options(options: list[str]) -> None:
    if not options:
        raise ValueError("At least one option is required to build a spin GIF.")


async def build_spin_gif_file(options: list[str]) -> tuple[discord.File, str]:
    """Build an animated GIF of the spin animation (non-blocking).

    Offloads CPU-intensive image processing to thread pool.
    Returns (discord.File of GIF, winning option string).
    """
    _validate_options(options)
    start_time = time.perf_counter()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_GIF_EXECUTOR, _build_spin_gif_sync, options)
    elapsed = time.perf_counter() - start_time
    logger.debug(f"GIF generation completed in {elapsed:.2f}s ({len(options)} options)")
    return result


def _consume_frames_to_rgb(frames: list[Image.Image]) -> list[Image.Image]:
    """Convert and close input frames, consuming the supplied list."""
    rgb_frames: list[Image.Image] = []
    for frame in frames:
        try:
            rgb_frames.append(frame.convert("RGB"))
        finally:
            frame.close()
    frames.clear()
    return rgb_frames


def _palette_sample_indices() -> tuple[int, int, int, int]:
    """Choose one representative frame from each animation phase."""
    fadeout_start = SPIN_FRAMES
    confetti_start = fadeout_start + FADEOUT_FRAMES
    outro_start = confetti_start + CONFETTI_FRAMES
    return (
        SPIN_FRAMES // 2,
        fadeout_start + FADEOUT_FRAMES // 2,
        confetti_start + CONFETTI_FRAMES // 2,
        outro_start + OUTRO_FRAMES // 2,
    )


def _create_gif_palette(frames: list[Image.Image]) -> Image.Image:
    """Build one shared color palette from representative phase frames."""
    sample_indices = _palette_sample_indices()
    palette_strip = Image.new("RGB", (GIF_WIDTH * len(sample_indices), GIF_HEIGHT))
    try:
        for strip_index, frame_index in enumerate(sample_indices):
            palette_strip.paste(frames[frame_index], (strip_index * GIF_WIDTH, 0))
        return palette_strip.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    finally:
        palette_strip.close()


def _quantize_frames(
    frames: list[Image.Image], palette: Image.Image
) -> list[Image.Image]:
    """Use shared palette without dithering to prevent flicker and retain crisp edges."""
    return [
        frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames
    ]


def _encode_gif_frames(frames: list[Image.Image]) -> io.BytesIO:
    """Serialize indexed frames as a looping GIF and close consumed frames."""
    gif_buffer = io.BytesIO()
    try:
        frames[0].save(
            gif_buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=FRAME_DURATION_MS,
            loop=0,
            # Palette is already shared; skip Pillow's CPU-heavy optimization pass.
            optimize=False,
        )
        gif_buffer.seek(0)
        return gif_buffer
    finally:
        for frame in frames:
            frame.close()


def _build_spin_gif_sync(options: list[str]) -> tuple[discord.File, str]:
    """Synchronous GIF generation - runs in thread pool.

    All PIL operations happen here to avoid blocking the event loop.
    """
    rng = random.Random()
    options = rng.sample(options, len(options))  # shuffle options
    selected_index = rng.randint(0, len(options) - 1)

    pipeline_started = time.perf_counter()
    frames = build_spin_frames(options, selected_index)
    rendered_at = time.perf_counter()

    rgb_frames = _consume_frames_to_rgb(frames)
    converted_at = time.perf_counter()

    palette = None
    try:
        palette = _create_gif_palette(rgb_frames)
        palette_at = time.perf_counter()

        quantized = _quantize_frames(rgb_frames, palette)
        quantized_at = time.perf_counter()
    finally:
        for frame in rgb_frames:
            frame.close()
        rgb_frames.clear()
        if palette is not None:
            palette.close()

    gif_buffer = _encode_gif_frames(quantized)
    encoded_at = time.perf_counter()
    logger.debug(
        f"GIF stage timings: render={rendered_at - pipeline_started:.3f}s "
        f"convert={converted_at - rendered_at:.3f}s "
        f"palette={palette_at - converted_at:.3f}s "
        f"quantize={quantized_at - palette_at:.3f}s "
        f"encode={encoded_at - quantized_at:.3f}s"
    )

    # Validate file size before returning
    file_size = gif_buffer.getbuffer().nbytes
    if file_size > MAX_GIF_SIZE:
        gif_buffer.close()
        raise ValueError(
            f"Generated GIF size ({file_size / (1024 * 1024):.1f} MB) "
            f"exceeds Discord's free tier limit ({MAX_GIF_SIZE / (1024 * 1024):.0f} MB)"
        )

    return discord.File(fp=gif_buffer, filename="spin.gif"), options[selected_index]
