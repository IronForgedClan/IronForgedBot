import unittest
from typing import NotRequired, TypedDict
from unittest.mock import mock_open, patch

from ironforgedbot.storage.data import load_json_data


class TestSkill(TypedDict):
    name: str
    display_name: NotRequired[str]
    order: int


_test_file = "test.json"


class TestDataLoader(unittest.TestCase):
    @patch("logging.error")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="hello world",
    )
    def test_load_json_data_fail_invalid_json(self, mock_file, mock_log):
        result = load_json_data(_test_file, TestSkill)
        self.assertIsNone(result)
        mock_file.assert_called_once_with(_test_file, "r")
        mock_log.assert_called_once_with("Expecting value: line 1 column 1 (char 0)")

    @patch("logging.error")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"name": "hitpoints", "order": 1}',
    )
    def test_load_json_data_fail_no_list(self, mock_file, mock_log):
        result = load_json_data(_test_file, TestSkill)
        self.assertIsNone(result)
        mock_file.assert_called_once_with(_test_file, "r")
        mock_log.assert_called_once_with(
            f"{_test_file}: does not contain an array/list"
        )

    @patch("logging.error")
    @patch("builtins.open", new_callable=mock_open, read_data='["hitpoints"]')
    def test_load_json_data_fail_no_object(self, mock_file, mock_log):
        result = load_json_data(_test_file, TestSkill)
        self.assertIsNone(result)
        mock_file.assert_called_once_with(_test_file, "r")
        mock_log.assert_called_once_with(f"{_test_file}: does not contain object/dict")

    @patch("logging.error")
    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "hitpoints"}]')
    def test_load_json_data_fail_missing_key(self, mock_file, mock_log):
        result = load_json_data(_test_file, TestSkill)
        self.assertIsNone(result)
        mock_file.assert_called_once_with(_test_file, "r")
        mock_log.assert_called_once_with(
            f"{_test_file}: object missing key (order) for type (TestSkill)"
        )

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='[{"name": "hitpoints", "order": 1}]',
    )
    def test_load_json_data_populate_optional_fields_if_empty(self, mock_file):
        result = load_json_data(_test_file, TestSkill)
        expected = [{"name": "hitpoints", "display_name": None, "order": 1}]
        self.assertEqual(expected, result)
        mock_file.assert_called_once_with(_test_file, "r")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='[{"name": "hitpoints", "display_name": "hp", "order": 1}]',
    )
    def test_load_json_data(self, mock_file):
        result = load_json_data(_test_file, TestSkill)
        expected = [{"name": "hitpoints", "display_name": "hp", "order": 1}]
        self.assertEqual(expected, result)
        mock_file.assert_called_once_with(_test_file, "r")
