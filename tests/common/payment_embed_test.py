import json
import unittest
from unittest.mock import mock_open, patch

import discord

from ironforgedbot.common.payment_embed import (
    COMMAND_PRICE_DATA_FILE,
    COINS_THUMBNAIL_URL,
    DEFAULT_PAYMENT_TITLE,
    build_payment_embed,
    load_flavor_text,
)


class TestLoadFlavorText(unittest.TestCase):
    def test_returns_list(self):
        fake_data = json.dumps({"flavor_text": ["alpha", "beta"]})
        with patch("builtins.open", mock_open(read_data=fake_data)):
            result = load_flavor_text()
        self.assertEqual(result, ["alpha", "beta"])

    def test_default_file_path(self):
        fake_data = json.dumps({"flavor_text": []})
        with patch("builtins.open", mock_open(read_data=fake_data)) as mock_file:
            load_flavor_text()
            mock_file.assert_called_once_with(COMMAND_PRICE_DATA_FILE)

    def test_custom_file_path(self):
        fake_data = json.dumps({"flavor_text": ["x"]})
        with patch("builtins.open", mock_open(read_data=fake_data)) as mock_file:
            load_flavor_text("custom/path.json")
            mock_file.assert_called_once_with("custom/path.json")

    def test_raises_on_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError("nope")):
            with self.assertRaises(FileNotFoundError):
                load_flavor_text()

    def test_raises_on_invalid_json(self):
        with patch("builtins.open", mock_open(read_data="not json")):
            with self.assertRaises(ValueError):
                load_flavor_text()

    def test_raises_on_missing_key(self):
        with patch("builtins.open", mock_open(read_data=json.dumps({"other": []}))):
            with self.assertRaises(KeyError):
                load_flavor_text()

    def test_raises_runtime_on_unexpected(self):
        with patch("builtins.open", side_effect=OSError("disk error")):
            with self.assertRaises(RuntimeError):
                load_flavor_text()


class TestBuildPaymentEmbed(unittest.TestCase):
    def _fields_by_name(self, embed):
        return {f.name: f.value for f in embed.fields}

    def test_default_title_and_color(self):
        embed = build_payment_embed(cost=100, user_balance=500)
        self.assertEqual(embed.title, DEFAULT_PAYMENT_TITLE)
        self.assertEqual(embed.color.value, discord.Colour.gold().value)

    def test_custom_title(self):
        embed = build_payment_embed(
            cost=100, user_balance=500, title="\U0001f4b0 Custom Title"
        )
        self.assertEqual(embed.title, "\U0001f4b0 Custom Title")

    def test_includes_balance_cost_expiration_fields(self):
        embed = build_payment_embed(cost=2500, user_balance=12345)
        fields = self._fields_by_name(embed)
        self.assertIn("Your Balance", fields)
        self.assertIn("Price", fields)
        self.assertIn("12,345", fields["Your Balance"])
        self.assertIn("2,500", fields["Price"])
        expiration_field = next((f for f in embed.fields if f.name == ""), None)
        self.assertIsNotNone(expiration_field)
        self.assertIn("expires", expiration_field.value.lower())

    def test_balance_and_cost_are_inline(self):
        embed = build_payment_embed(cost=100, user_balance=500)
        for field in embed.fields:
            if field.name in ("Your Balance", "Price"):
                self.assertTrue(field.inline)

    def test_expiration_field_is_not_inline(self):
        embed = build_payment_embed(cost=100, user_balance=500)
        for field in embed.fields:
            if field.name == "":
                self.assertFalse(field.inline)

    def test_includes_flavor_text_in_description(self):
        embed = build_payment_embed(cost=100, user_balance=500, flavor_text="*hello*")
        self.assertIn("hello", embed.description)

    def test_no_flavor_text_yields_empty_description(self):
        embed = build_payment_embed(cost=100, user_balance=500)
        self.assertEqual(embed.description, "")

    def test_thumbnail_set(self):
        embed = build_payment_embed(cost=100, user_balance=500)
        self.assertIsNotNone(embed.thumbnail)
        self.assertEqual(embed.thumbnail.url, COINS_THUMBNAIL_URL)

    def test_custom_thumbnail(self):
        embed = build_payment_embed(
            cost=100, user_balance=500, thumbnail_url="https://example.com/x.png"
        )
        self.assertEqual(embed.thumbnail.url, "https://example.com/x.png")

    def test_expiration_field_format(self):
        embed = build_payment_embed(cost=100, user_balance=500)
        expiration_field = next(f for f in embed.fields if f.name == "")
        self.assertIn("<t:", expiration_field.value)
        self.assertIn(":R>", expiration_field.value)
