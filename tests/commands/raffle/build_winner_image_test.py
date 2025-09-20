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
        image = await build_winner_image_file("oxore", 5123456)
        
        # Verify the image was created and has content
        self.assertIsNotNone(image)
        self.assertIsNotNone(image.fp)
        
        # Verify the image has reasonable size (not empty, not too large)
        image_data = image.fp.read()
        self.assertGreater(len(image_data), 1000)  # At least 1KB
        self.assertLess(len(image_data), 1000000)  # Less than 1MB
        
        # Verify it's a PNG file by checking magic bytes
        image.fp.seek(0)
        magic_bytes = image.fp.read(8)
        self.assertEqual(magic_bytes, b'\x89PNG\r\n\x1a\n')
