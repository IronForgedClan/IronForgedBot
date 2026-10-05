import asyncio
import io
import logging
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor

import discord
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

GIF_WIDTH, GIF_HEIGHT = 500, 200
FRAME_DURATION_MS = 70  # GIF delays use 10 ms increments; ~14.3 fps
GIF_BACKGROUND_COLOR = (43, 45, 49, 255)
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

FRAME_COUNT = SPIN_FRAMES + FADEOUT_FRAMES + CONFETTI_FRAMES + OUTRO_FRAMES  # 165

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


def _create_text_masks(
    text: str, font: ImageFont.FreeTypeFont, outline_width: int = 2
) -> tuple[Image.Image, Image.Image, int, int]:
    """Rasterize text fill and outline once for reuse across animation frames."""
    left, top, right, bottom = font.getbbox(text, stroke_width=outline_width)
    size = (right - left, bottom - top)

    outline_mask = Image.new("L", size, 0)
    fill_mask = Image.new("L", size, 0)
    ImageDraw.Draw(outline_mask).text(
        (-left, -top),
        text,
        font=font,
        fill=255,
        stroke_width=outline_width,
        stroke_fill=255,
    )
    ImageDraw.Draw(fill_mask).text((-left, -top), text, font=font, fill=255)

    return outline_mask, fill_mask, left, top


def _draw_text_with_masks(
    draw: ImageDraw.Draw,
    x: float,
    y: float,
    masks: tuple[Image.Image, Image.Image, int, int],
    alpha: int,
) -> None:
    """Composite cached text masks at requested position and opacity."""
    outline_mask, fill_mask, left, top = masks
    position = (round(x) + left, round(y) + top)
    draw.bitmap(position, outline_mask, fill=(0, 0, 0, alpha))
    draw.bitmap(position, fill_mask, fill=(255, 255, 0, alpha))


def build_spin_frames(options: list[str], selected_index: int) -> list[Image.Image]:
    """Build all animation frames for the spin.

    Returns a list of FRAME_COUNT RGBA images across four phases:
    - Phase 1 (SPIN_FRAMES): spinning slot animation (text fades in over FADEIN_FRAMES)
    - Phase 2 (FADEOUT_FRAMES): non-winners fade out
    - Phase 3 (CONFETTI_FRAMES): confetti rain while winner stays centred
    - Phase 4 (OUTRO_FRAMES): everything fades out to pure background (loop point)
    """
    total_scroll_items = (
        math.ceil(FIXED_SCROLL_ITEMS / len(options)) * len(options) + selected_index
    )
    total_scroll_px = total_scroll_items * ITEM_HEIGHT

    font = ImageFont.truetype(FONT_PATH, size=FONT_SIZE)
    center_y = GIF_HEIGHT / 2
    background = _ensure_opaque_background(_load_background())
    text_layout = {}
    for text in set(options):
        bbox = font.getbbox(text)
        x = (GIF_WIDTH - (bbox[2] - bbox[0])) // 2
        text_layout[text] = (bbox, x, _create_text_masks(text, font))

    frames: list[Image.Image] = []

    # Phase 1: spin
    for i in range(SPIN_FRAMES):
        t = i / (SPIN_FRAMES - 1)
        scroll = total_scroll_px * _ease_out_cubic(t)

        # Snap last 5 frames to exact final position to eliminate end-of-spin jitter
        if i >= SPIN_FRAMES - 5:
            scroll = total_scroll_px

        scroll_items = scroll / ITEM_HEIGHT
        base_index = int(scroll_items)
        frac = scroll_items - base_index
        # Clamp near-integer frac to avoid boundary flicker
        if frac > 1 - 1e-3:
            frac = 0.0
            base_index += 1

        # Fade-in multiplier: 0.0 at i=0, 1.0 at i>=FADEIN_FRAMES-1
        fadein_alpha = min(1.0, i / (FADEIN_FRAMES - 1))

        overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for n in range(-3, 4):
            item_y = center_y + (n - frac) * ITEM_HEIGHT
            item_index = (base_index + n) % len(options)
            text = options[item_index]

            alpha = _get_text_alpha(abs(item_y - center_y), ITEM_HEIGHT)
            alpha = int(alpha * fadein_alpha)
            if alpha == 0:
                continue

            bbox, x, masks = text_layout[text]
            text_y = item_y - (bbox[3] - bbox[1]) / 2 - bbox[1]

            _draw_text_with_masks(draw, x, text_y, masks, alpha)

        composite = Image.alpha_composite(background, overlay)
        frames.append(composite)

    # Phase 2: fade-out
    final_base_index = total_scroll_items  # frac = 0 at final position

    for f in range(FADEOUT_FRAMES):
        progress = f / (FADEOUT_FRAMES - 1)  # 0.0 -> 1.0
        overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for n in range(-3, 4):
            item_y = center_y + n * ITEM_HEIGHT  # frac = 0 -> exact slot positions
            item_index = (final_base_index + n) % len(options)
            text = options[item_index]

            if item_index == selected_index:
                alpha = 255
            else:
                base_alpha = _get_text_alpha(abs(item_y - center_y), ITEM_HEIGHT)
                alpha = int(base_alpha * (1.0 - progress))

            if alpha == 0:
                continue

            bbox, x, masks = text_layout[text]
            text_y = item_y - (bbox[3] - bbox[1]) / 2 - bbox[1]
            _draw_text_with_masks(draw, x, text_y, masks, alpha)

        composite = Image.alpha_composite(background, overlay)
        frames.append(composite)

    # Phases 3 & 4: confetti then outro
    # Particle physics and winner text are seeded once; the time index f runs
    # continuously across both phases so confetti motion is uninterrupted.
    rng = random.Random(selected_index)
    particles = [
        (
            rng.randint(0, GIF_WIDTH - CONFETTI_SIZE),  # px0
            rng.uniform(-GIF_HEIGHT, 0),  # py0 (starts above screen)
            rng.uniform(-2.0, 2.0),  # vx
            rng.uniform(3.0, 6.0),  # vy
            rng.choice(CONFETTI_COLORS),  # color
        )
        for _ in range(CONFETTI_COUNT)
    ]

    # Pre-compute winner text layout (constant for all confetti frames)
    winner_text = options[selected_index]
    w_bbox, winner_x, winner_masks = text_layout[winner_text]
    winner_ty = center_y - (w_bbox[3] - w_bbox[1]) / 2 - w_bbox[1]

    # Phase 3 (f < CONFETTI_FRAMES): winner text + confetti at full opacity.
    # Phase 4 (f >= CONFETTI_FRAMES): same, but both fade out linearly to 0.
    for f in range(CONFETTI_FRAMES + OUTRO_FRAMES):
        outro_f = f - CONFETTI_FRAMES  # negative during phase 3
        fade = 1.0 if outro_f < 0 else 1.0 - outro_f / (OUTRO_FRAMES - 1)
        alpha = int(255 * fade)

        text_overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        _draw_text_with_masks(
            ImageDraw.Draw(text_overlay), winner_x, winner_ty, winner_masks, alpha
        )

        confetti_overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        cd = ImageDraw.Draw(confetti_overlay)
        for px0, py0, vx, vy, color in particles:
            px = int((px0 + vx * f) % GIF_WIDTH)
            py = int(py0 + vy * f)
            if 0 <= py < GIF_HEIGHT:
                cd.rectangle(
                    [px, py, px + CONFETTI_SIZE - 1, py + CONFETTI_SIZE - 1],
                    fill=(*color, alpha),
                )

        composite = Image.alpha_composite(background, text_overlay)
        composite = Image.alpha_composite(composite, confetti_overlay)
        frames.append(composite)

    return frames


async def build_spin_gif_file(options: list[str]) -> tuple[discord.File, str]:
    """Build an animated GIF of the spin animation (non-blocking).

    Offloads CPU-intensive image processing to thread pool.
    Returns (discord.File of GIF, winning option string).
    """
    start_time = time.perf_counter()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_GIF_EXECUTOR, _build_spin_gif_sync, options)
    elapsed = time.perf_counter() - start_time
    logger.debug(f"GIF generation completed in {elapsed:.2f}s ({len(options)} options)")
    return result


def _convert_frames_to_rgb(frames: list[Image.Image]) -> list[Image.Image]:
    """Convert frames while releasing each larger RGBA source immediately."""
    gif_frames = []
    for frame in frames:
        try:
            gif_frames.append(frame.convert("RGB"))
        finally:
            frame.close()
    frames.clear()
    return gif_frames


def _build_spin_gif_sync(options: list[str]) -> tuple[discord.File, str]:
    """Synchronous GIF generation - runs in thread pool.

    All PIL operations happen here to avoid blocking the event loop.
    """
    rng = random.Random()
    options = rng.sample(options, len(options))  # shuffle options
    selected_index = rng.randint(0, len(options) - 1)

    # build_spin_frames returns RGBA images so each phase can composite
    # transparent overlays (text, confetti) onto the background independently.
    pipeline_started = time.perf_counter()
    frames = build_spin_frames(options, selected_index)
    rendered_at = time.perf_counter()

    # build_spin_frames guarantees an opaque background, so conversion alone
    # preserves pixels and avoids another full-frame composite pass.
    gif_frames = _convert_frames_to_rgb(frames)
    del frames
    converted_at = time.perf_counter()

    # We sample one frame from each animation phase (spin, fadeout, confetti,
    # outro) and tile them side-by-side before quantizing. This ensures palette
    # entries cover all colour states: spin text, confetti colours, background
    # variants, and fade intermediates, rather than being dominated by a single frame.
    sample_indices = [
        SPIN_FRAMES // 2,  # mid-spin
        SPIN_FRAMES + FADEOUT_FRAMES // 2,  # mid-fadeout
        SPIN_FRAMES + FADEOUT_FRAMES + CONFETTI_FRAMES // 2,  # mid-confetti
        SPIN_FRAMES + FADEOUT_FRAMES + CONFETTI_FRAMES + OUTRO_FRAMES // 2,  # mid-outro
    ]
    palette_strip = Image.new("RGB", (GIF_WIDTH * len(sample_indices), GIF_HEIGHT))
    for i, idx in enumerate(sample_indices):
        palette_strip.paste(gif_frames[idx], (i * GIF_WIDTH, 0))

    # MEDIANCUT distributes palette entries by colour population, giving the
    # best coverage within the 256-colour GIF limit without biasing towards any
    # single hue.
    palette_source = palette_strip.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    del palette_strip
    palette_at = time.perf_counter()

    # All frames are quantized to the same palette so the colour mapping is
    # identical across every frame. A per-frame palette would cause visible
    # colour shifting between frames (palette flicker). Dither=NONE produces
    # clean, hard edges on text and confetti squares; ordered or error-diffusion
    # dithering would add noise patterns that are distracting on flat regions.
    quantized = [
        f.quantize(palette=palette_source, dither=Image.Dither.NONE) for f in gif_frames
    ]
    del gif_frames, palette_source
    quantized_at = time.perf_counter()

    gif_buffer = io.BytesIO()
    quantized[0].save(
        gif_buffer,
        format="GIF",
        save_all=True,
        append_images=quantized[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
    )
    gif_buffer.seek(0)
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
        raise ValueError(
            f"Generated GIF size ({file_size / (1024 * 1024):.1f} MB) "
            f"exceeds Discord's free tier limit ({MAX_GIF_SIZE / (1024 * 1024):.0f} MB)"
        )

    return discord.File(fp=gif_buffer, filename="spin.gif"), options[selected_index]
