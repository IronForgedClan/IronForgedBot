import unittest

from ironforgedbot.common.text_formatters import (
    text_ascii_table,
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
        expected = f"-# {value}\n"
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
        expected = f"# {value}\n"
        result = text_h1(value)
        self.assertEqual(result, expected)

    def test_text_h2(self):
        value = "test"
        expected = f"## {value}\n"
        result = text_h2(value)
        self.assertEqual(result, expected)

    def test_text_h3(self):
        value = "test"
        expected = f"### {value}\n"
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
        expected = f"> {value}\n"
        result = text_quote(value)
        self.assertEqual(result, expected)

    def test_text_quote_multiline(self):
        value = "test"
        expected = f">>> {value}\n"
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


class TestTextAsciiTable(unittest.TestCase):
    def test_default_renders_code_block_table(self):
        result = text_ascii_table(
            [("a", "1"), ("bb", "22")],
            headers=["A", "B"],
        )
        self.assertTrue(result.startswith("```"))
        self.assertTrue(result.endswith("```"))
        self.assertIn("A", result)
        self.assertIn("B", result)
        self.assertIn("a", result)
        self.assertIn("22", result)

    def test_no_code_block_returns_raw_tabulate(self):
        result = text_ascii_table(
            [("a", "1")],
            headers=["A", "B"],
            code_block=False,
        )
        self.assertFalse(result.startswith("```"))
        self.assertFalse(result.endswith("```"))
        self.assertIn("A", result)

    def test_no_wrap_passes_cells_through(self):
        result = text_ascii_table(
            [("short", "1")],
            headers=["Label", "Value"],
            code_block=False,
        )
        self.assertIn("short", result)
        self.assertNotIn("short\n", result)

    def test_wrap_widths_per_column(self):
        result = text_ascii_table(
            [("chambers of xeric", "100,000")],
            headers=["Point", "Remaining"],
            wrap_widths=[10, None],
            code_block=False,
        )
        lines = result.split("\n")
        same_line = [ln for ln in lines if "chambers" in ln and "of xeric" in ln]
        self.assertEqual(
            len(same_line),
            0,
            f"expected wrap to split 'chambers' and 'of xeric' across lines; got: {result!r}",
        )
        self.assertTrue(any("chambers" in ln for ln in lines))
        self.assertTrue(any("of xeric" in ln for ln in lines))

    def test_break_long_words_force_breaks(self):
        long = "a" * 30
        result = text_ascii_table(
            [(long, "1")],
            headers=["Label", "Value"],
            wrap_widths=[8, None],
            code_block=False,
        )
        for line in result.split("\n"):
            if line.strip().startswith("|"):
                first_cell = line.strip().strip("|").split("|")[0].strip()
                if first_cell and all(c == "a" for c in first_cell):
                    self.assertLessEqual(len(first_cell), 8)

    def test_short_value_passes_through_unwrapped(self):
        result = text_ascii_table(
            [("Attack", "1")],
            headers=["Skill", "Value"],
            wrap_widths=[20, None],
            code_block=False,
        )
        self.assertIn("Attack", result)

    def test_tablefmt_pass_through(self):
        result = text_ascii_table(
            [("a", "1")],
            headers=["A", "B"],
            tablefmt="github",
            code_block=False,
        )
        self.assertIn("|", result)
        self.assertIn("---", result)

    def test_colalign_pass_through(self):
        result = text_ascii_table(
            [("a", "1"), ("bb", "22")],
            headers=["A", "B"],
            colalign=("right", "left"),
            code_block=False,
        )
        self.assertIn("a", result)
        self.assertIn("22", result)

    def test_empty_headers_yields_headerless_table(self):
        result = text_ascii_table(
            [("a", "1"), ("b", "2")],
            code_block=False,
        )
        self.assertNotIn("| A |", result)

    def test_empty_rows_renders_headers_only(self):
        result = text_ascii_table(
            [],
            headers=["A", "B"],
            code_block=False,
        )
        self.assertIn("A", result)
        self.assertIn("B", result)

    def test_none_value_in_wrapped_column_passes_through(self):
        result = text_ascii_table(
            [("", "1")],
            headers=["Label", "Value"],
            wrap_widths=[10, None],
            code_block=False,
        )
        self.assertIn("1", result)
