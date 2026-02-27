import io
import os
import random
import tempfile

import av
import discord
from PIL import Image, ImageDraw, ImageFont

GIF_WIDTH, GIF_HEIGHT = 500, 200
FRAME_DURATION_MS = 67
NUM_SPINS = 5
FONT_SIZE = 40
ITEM_HEIGHT = 50

SPIN_FRAMES = 100
FADEOUT_FRAMES = 20
CONFETTI_FRAMES = 75
FADEIN_FRAMES = 15  # first N spin frames where all text fades in (0→1)
OUTRO_FRAMES = 25  # after confetti: everything fades out (1→0) → pure background

FRAME_COUNT = SPIN_FRAMES + FADEOUT_FRAMES + CONFETTI_FRAMES + OUTRO_FRAMES  # 220

CONFETTI_COUNT = 80
CONFETTI_SIZE = 6  # px square
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

BACKGROUND_IMAGE_PATH = "img/spin_background.png"
FONT_PATH = "fonts/runescape.ttf"


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _get_text_alpha(distance: float, item_height: int) -> int:
    alpha = max(0.0, 1.0 - distance / (item_height * 1.5))
    return int(alpha * 255)


def _load_background() -> Image.Image:
    try:
        img = Image.open(BACKGROUND_IMAGE_PATH).convert("RGBA")
        return img.resize((GIF_WIDTH, GIF_HEIGHT))
    except FileNotFoundError:
        return Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (20, 20, 40, 255))


def _draw_text_with_outline_rgba(
    draw: ImageDraw.Draw,
    x: float,
    y: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    alpha: int,
    outline_width: int = 2,
):
    outline_color = (0, 0, 0, alpha)
    fill_color = (255, 255, 0, alpha)

    for offset_x, offset_y in [
        (-outline_width, 0),
        (outline_width, 0),
        (0, -outline_width),
        (0, outline_width),
        (-outline_width, -outline_width),
        (-outline_width, outline_width),
        (outline_width, -outline_width),
        (outline_width, outline_width),
    ]:
        draw.text((x + offset_x, y + offset_y), text, font=font, fill=outline_color)

    draw.text((x, y), text, font=font, fill=fill_color)


def build_spin_frames(options: list[str], selected_index: int) -> list[Image.Image]:
    """Build all animation frames for the spin.

    Returns a list of FRAME_COUNT RGBA images across four phases:
    - Phase 1 (SPIN_FRAMES): spinning slot animation (text fades in over FADEIN_FRAMES)
    - Phase 2 (FADEOUT_FRAMES): non-winners fade out
    - Phase 3 (CONFETTI_FRAMES): confetti rain while winner stays centred
    - Phase 4 (OUTRO_FRAMES): everything fades out to pure background (loop point)
    """
    total_scroll_items = NUM_SPINS * len(options) + selected_index
    total_scroll_px = total_scroll_items * ITEM_HEIGHT

    font = ImageFont.truetype(FONT_PATH, size=FONT_SIZE)
    center_y = GIF_HEIGHT / 2
    background = _load_background()

    frames: list[Image.Image] = []

    # --- Phase 1: Spin ---
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

        bg_copy = background.copy()
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

            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            x = (GIF_WIDTH - text_width) // 2
            text_y = item_y - (bbox[3] - bbox[1]) / 2 - bbox[1]

            _draw_text_with_outline_rgba(draw, x, text_y, text, font, alpha)

        composite = Image.alpha_composite(bg_copy, overlay)
        frames.append(composite)

    # --- Phase 2: Fade-out ---
    final_base_index = total_scroll_items  # frac = 0 at final position

    for f in range(FADEOUT_FRAMES):
        progress = f / (FADEOUT_FRAMES - 1)  # 0.0 → 1.0
        bg_copy = background.copy()
        overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for n in range(-3, 4):
            item_y = center_y + n * ITEM_HEIGHT  # frac = 0 → exact slot positions
            item_index = (final_base_index + n) % len(options)
            text = options[item_index]

            if item_index == selected_index:
                alpha = 255
            else:
                base_alpha = _get_text_alpha(abs(item_y - center_y), ITEM_HEIGHT)
                alpha = int(base_alpha * (1.0 - progress))

            if alpha == 0:
                continue

            bbox = font.getbbox(text)
            x = (GIF_WIDTH - (bbox[2] - bbox[0])) // 2
            text_y = item_y - (bbox[3] - bbox[1]) / 2 - bbox[1]
            _draw_text_with_outline_rgba(draw, x, text_y, text, font, alpha)

        composite = Image.alpha_composite(bg_copy, overlay)
        frames.append(composite)

    # --- Phase 3: Confetti ---
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
    w_bbox = font.getbbox(winner_text)
    winner_x = (GIF_WIDTH - (w_bbox[2] - w_bbox[0])) // 2
    winner_ty = center_y - (w_bbox[3] - w_bbox[1]) / 2 - w_bbox[1]

    for f in range(CONFETTI_FRAMES):
        bg_copy = background.copy()

        # Layer 1: winner text
        text_overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        _draw_text_with_outline_rgba(
            ImageDraw.Draw(text_overlay), winner_x, winner_ty, winner_text, font, 255
        )

        # Layer 2: confetti squares
        confetti_overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        cd = ImageDraw.Draw(confetti_overlay)
        for px0, py0, vx, vy, color in particles:
            px = int((px0 + vx * f) % GIF_WIDTH)
            py = int(py0 + vy * f)
            if 0 <= py < GIF_HEIGHT:
                cd.rectangle(
                    [px, py, px + CONFETTI_SIZE - 1, py + CONFETTI_SIZE - 1],
                    fill=(*color, 255),
                )

        # Composite: background → text → confetti
        composite = Image.alpha_composite(bg_copy, text_overlay)
        composite = Image.alpha_composite(composite, confetti_overlay)
        frames.append(composite)

    # --- Phase 4: Outro (fade everything out to pure background) ---
    for f in range(OUTRO_FRAMES):
        progress = f / (OUTRO_FRAMES - 1)  # 0.0 → 1.0
        fade_alpha = int(255 * (1.0 - progress))  # 255 → 0
        virtual_f = CONFETTI_FRAMES + f  # continue confetti motion

        bg_copy = background.copy()

        # Winner text (fading out)
        text_overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        _draw_text_with_outline_rgba(
            ImageDraw.Draw(text_overlay),
            winner_x,
            winner_ty,
            winner_text,
            font,
            fade_alpha,
        )

        # Confetti (continuing motion + fading out)
        confetti_overlay = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 0))
        cd = ImageDraw.Draw(confetti_overlay)
        for px0, py0, vx, vy, color in particles:
            px = int((px0 + vx * virtual_f) % GIF_WIDTH)
            py = int(py0 + vy * virtual_f)
            if 0 <= py < GIF_HEIGHT:
                cd.rectangle(
                    [px, py, px + CONFETTI_SIZE - 1, py + CONFETTI_SIZE - 1],
                    fill=(*color, fade_alpha),
                )

        composite = Image.alpha_composite(bg_copy, text_overlay)
        composite = Image.alpha_composite(composite, confetti_overlay)
        frames.append(composite)

    return frames


async def build_spin_webm_file(options: list[str]) -> tuple[discord.File, str]:
    """Returns (discord.File of WebM, winning option string)."""
    selected_index = random.randint(0, len(options) - 1)
    frames = build_spin_frames(options, selected_index)
    fps = 1000 / FRAME_DURATION_MS  # ≈ 14.93
    _solid = Image.new("RGBA", (GIF_WIDTH, GIF_HEIGHT), (0, 0, 0, 255))

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp_path = tmp.name

    with av.open(tmp_path, mode="w", format="webm") as container:
        stream = container.add_stream("vp9", rate=round(fps))
        stream.width = GIF_WIDTH
        stream.height = GIF_HEIGHT
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "30", "b:v": "0"}

        for rgba_frame in frames:
            rgb = Image.alpha_composite(_solid, rgba_frame).convert("RGB")
            av_frame = av.VideoFrame.from_image(rgb)
            for packet in stream.encode(av_frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)

    with open(tmp_path, "rb") as f:
        webm_binary = io.BytesIO(f.read())
    os.unlink(tmp_path)

    webm_binary.seek(0)
    return discord.File(fp=webm_binary, filename="spin.webm"), options[selected_index]
