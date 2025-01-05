import io
from typing import Any, Tuple
from PIL import Image, ImageDraw, ImageFont
import discord


async def build_winner_image_file(winner_name: str, winnings: int) -> discord.File:
    image_path = "img/raffle_winner.jpeg"

    def calculate_position(
        text,
        font: ImageFont.FreeTypeFont,
    ) -> Tuple[float, float]:
        text = str(text)
        bbox = font.getbbox(text)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        image_width, image_height = img.size
        x = (image_width - text_width) // 2
        y = (image_height - text_height) // 2

        return x, y

    def draw_text_with_outline(
        draw: ImageDraw.Draw,
        x: float,
        y: float,
        text: str,
        font: ImageFont.FreeTypeFont,
        outline_color: Any = "black",
        fill_color: Any = "yellow",
        outline_width: int = 2,
    ):
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

    with Image.open(image_path) as img:
        draw = ImageDraw.Draw(img)

        # draw winner name
        font = ImageFont.truetype("fonts/runescape.ttf", size=85)
        x, y = calculate_position(winner_name, font)
        y = y - 65  # offset

        draw_text_with_outline(draw, x, y, winner_name, font)

        # draw winner quantity with icon
        spacing = 10
        offset = 90
        winnings_text = f"{winnings:,}"
        font = ImageFont.truetype("fonts/runescape.ttf", size=40)

        icon = Image.open("img/ingot_icon.png").convert("RGBA")
        icon = icon.resize((35, 35))
        icon_width, icon_height = icon.size

        text_bbox = font.getbbox(winnings_text)
        text_width, text_height = (
            text_bbox[2] - text_bbox[0],
            text_bbox[3] - text_bbox[1],
        )

        total_width = text_width + spacing + icon_width
        x_start = (img.width - total_width) // 2

        # Calculate positions
        icon_x = x_start
        icon_y = (y + (text_height - icon_height) // 2) + offset
        text_x = x_start + icon_width + spacing
        text_y = y + offset

        draw_text_with_outline(draw, text_x, text_y, winnings_text, font)
        img.paste(icon, (icon_x, icon_y), mask=icon)

        # Return discord.File
        with io.BytesIO() as image_binary:
            img.save(image_binary, "PNG")
            image_binary.seek(0)
            return discord.File(fp=image_binary, filename="raffle_winner.png")
