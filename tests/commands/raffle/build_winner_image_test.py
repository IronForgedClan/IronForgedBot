import hashlib
import unittest

from PIL import ImageFont

from ironforgedbot.commands.raffle.build_winner_image import (
    _calculate_position,
    build_winner_image_file,
)


class TestBuildWinnerImage(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = ImageFont.truetype("./fonts/runescape.ttf", size=50)

    def test_centered_position_basic(self):
        text = "123456789012"
        image_width = 200
        image_height = 200

        x, y = _calculate_position(text, self.font, image_width, image_height)

        bbox = self.font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        expected_x = (image_width - text_width) // 2
        expected_y = (image_height - text_height) // 2

        self.assertEqual(x, expected_x)
        self.assertEqual(y, expected_y)

    def test_empty_text(self):
        text = ""
        image_width = 200
        image_height = 200

        x, y = _calculate_position(text, self.font, image_width, image_height)

        expected_x = image_width // 2
        expected_y = image_height // 2

        self.assertEqual(x, expected_x)
        self.assertEqual(y, expected_y)

    async def test_image_generation(self):
        expected_hash = 0
        with open("./tests/commands/raffle/raffle_winner_reference.png", "rb") as f:
            expected_hash = hashlib.md5(f.read()).hexdigest()

        image = await build_winner_image_file("oxore", 5123456)

        self.assertEqual(
            expected_hash,
            hashlib.md5(image.fp.read()).hexdigest(),
        )
