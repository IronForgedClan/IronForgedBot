import json
import unittest
from typing import NotRequired, TypedDict
from unittest.mock import mock_open, patch

from ironforgedbot.storage.data import load_json_data


class TestActivity(TypedDict):
    name: str
    display_name: NotRequired[str]
    display_order: int


class DataTest(unittest.TestCase):
    def setUp(self):
        self.test_file = "test.json"

    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "vorkath", "display_name": "Vorkath", "display_order": 1}]')
    def test_load_json_data_success(self, mock_file):
        result = load_json_data(self.test_file, TestActivity)
        expected = [{"name": "vorkath", "display_name": "Vorkath", "display_order": 1}]
        
        self.assertEqual(result, expected)
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data="invalid json")
    def test_raises_json_decode_error_for_invalid_json(self, mock_file):
        with self.assertRaises(json.JSONDecodeError):
            load_json_data(self.test_file, TestActivity)
        
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='{"name": "vorkath", "display_order": 1}')
    def test_raises_type_error_when_not_list(self, mock_file):
        with self.assertRaises(TypeError) as context:
            load_json_data(self.test_file, TestActivity)
        
        self.assertIn("does not contain an array/list", str(context.exception))
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='["vorkath"]')
    def test_raises_type_error_when_not_dict_objects(self, mock_file):
        with self.assertRaises(TypeError) as context:
            load_json_data(self.test_file, TestActivity)
        
        self.assertIn("does not contain object/dict", str(context.exception))
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "vorkath"}]')
    def test_raises_key_error_for_missing_required_field(self, mock_file):
        with self.assertRaises(KeyError) as context:
            load_json_data(self.test_file, TestActivity)
        
        self.assertIn("object missing key (display_order)", str(context.exception))
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "vorkath", "display_order": 1}]')
    def test_populates_optional_fields_with_none(self, mock_file):
        result = load_json_data(self.test_file, TestActivity)
        expected = [{"name": "vorkath", "display_name": None, "display_order": 1}]
        
        self.assertEqual(result, expected)
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='[]')
    def test_raises_value_error_for_empty_list(self, mock_file):
        with self.assertRaises(ValueError) as context:
            load_json_data(self.test_file, TestActivity)
        
        self.assertIn("output result is invalid", str(context.exception))
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", new_callable=mock_open, read_data='[{"name": "vorkath", "display_order": 1}, {"name": "zulrah", "display_order": 2}]')
    def test_loads_multiple_items_successfully(self, mock_file):
        result = load_json_data(self.test_file, TestActivity)
        expected = [
            {"name": "vorkath", "display_name": None, "display_order": 1},
            {"name": "zulrah", "display_name": None, "display_order": 2}
        ]
        
        self.assertEqual(result, expected)
        mock_file.assert_called_once_with(self.test_file, "r")

    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    def test_handles_file_not_found_error(self, mock_file):
        with self.assertRaises(FileNotFoundError):
            load_json_data(self.test_file, TestActivity)
        
        mock_file.assert_called_once_with(self.test_file, "r")