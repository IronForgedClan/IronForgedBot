import unittest

from ironforgedbot.common.text_formatters import (
    text_bold,
    text_bold_italics,
    text_code,
    text_code_block,
    text_h1,
    text_h2,
    text_h3,
    text_italic,
    text_link,
    text_ol,
    text_quote,
    text_quote_multiline,
    text_sub,
    text_ul,
    text_underline,
)


class TestTextFormatters(unittest.TestCase):
    def test_text_bold(self):
        value = "test"
        expected = f"**{value}**"
        result = text_bold(value)
        self.assertEqual(result, expected)

    def test_text_italic(self):
        value = "test"
        expected = f"_{value}_"
        result = text_italic(value)
        self.assertEqual(result, expected)

    def test_text_bold_italics(self):
        value = "test"
        expected = f"***{value}***"
        result = text_bold_italics(value)
        self.assertEqual(result, expected)

    def test_text_underline(self):
        value = "test"
        expected = f"__{value}__"
        result = text_underline(value)
        self.assertEqual(result, expected)

    def test_text_sub(self):
        value = "test"
        expected = f"-# {value}"
        result = text_sub(value)
        self.assertEqual(result, expected)

    def test_text_link(self):
        value = "test"
        link = "http://example.com"
        expected = f"[{value}]({link})"
        result = text_link(value, link)
        self.assertEqual(result, expected)

    def test_text_h1(self):
        value = "test"
        expected = f"# {value}"
        result = text_h1(value)
        self.assertEqual(result, expected)

    def test_text_h2(self):
        value = "test"
        expected = f"## {value}"
        result = text_h2(value)
        self.assertEqual(result, expected)

    def test_text_h3(self):
        value = "test"
        expected = f"### {value}"
        result = text_h3(value)
        self.assertEqual(result, expected)

    def test_text_ul(self):
        value = ["one", "two", "three"]
        expected = "- one\n- two\n- three\n"
        result = text_ul(value)
        self.assertEqual(result, expected)

    def test_text_ol(self):
        value = ["one", "two", "three"]
        expected = "1. one\n2. two\n3. three\n"
        result = text_ol(value)
        self.assertEqual(result, expected)

    def test_text_quote(self):
        value = "test"
        expected = f"> {value}"
        result = text_quote(value)
        self.assertEqual(result, expected)

    def test_text_quote_multiline(self):
        value = "test"
        expected = f">>> {value}"
        result = text_quote_multiline(value)
        self.assertEqual(result, expected)

    def test_text_code(self):
        value = "test"
        expected = f"`{value}`"
        result = text_code(value)
        self.assertEqual(result, expected)

    def test_text_code_block(self):
        value = "test"
        expected = f"```{value}```"
        result = text_code_block(value)
        self.assertEqual(result, expected)
