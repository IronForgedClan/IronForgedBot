import json
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

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="hello world",
    )
    def test_load_json_data_fail_invalid_json(self, mock_file):
        with self.assertRaises(json.decoder.JSONDecodeError):
            load_json_data(_test_file, TestSkill)
            mock_file.assert_called_once_with(_test_file, "r")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"name": "hitpoints", "order": 1}',
    )
    def test_load_json_data_fail_no_list(self, mock_file):
        with self.assertRaises(TypeError):
            load_json_data(_test_file, TestSkill)
            mock_file.assert_called_once_with(_test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='["hitpoints"]')
    def test_load_json_data_fail_no_object(self, mock_file):
        with self.assertRaises(TypeError):
            load_json_data(_test_file, TestSkill)
            mock_file.assert_called_once_with(_test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "hitpoints"}]')
    def test_load_json_data_fail_missing_key(self, mock_file):
        with self.assertRaises(KeyError):
            load_json_data(_test_file, TestSkill)
            mock_file.assert_called_once_with(_test_file, "r")

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
