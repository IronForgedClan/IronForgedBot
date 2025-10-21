import unittest
from unittest.mock import mock_open, patch

import yaml

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    _load_values_file,
    _load_weights_file,
)


class TestLoadValuesFile(unittest.TestCase):
    """Test cases for the _load_values_file function."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_values = {
            "ingot_ranges": {
                "low_min": 100,
                "low_max": 500,
                "high_min": 600,
                "high_max": 1000,
            },
            "jackpot_value": 10000,
            "backrooms": {
                "door_count": 3,
                "treasure_min": 500,
                "treasure_max": 1500,
                "monster_min": 300,
                "monster_max": 800,
            },
            "quiz_master": {
                "correct_min": 200,
                "correct_max": 600,
                "wrong_penalty_min": 100,
                "wrong_penalty_max": 400,
                "penalty_chance": 0.5,
            },
        }

    def test_load_values_file_success(self):
        """Test successfully loading a valid values file."""
        yaml_content = yaml.dump(self.valid_values)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            result = _load_values_file("test_values.yaml")

        self.assertEqual(result, self.valid_values)
        mock_file.assert_called_once_with("test_values.yaml")

    def test_load_values_file_not_found(self):
        """Test that FileNotFoundError is raised when file doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError("test.yaml")):
            with self.assertRaises(FileNotFoundError) as context:
                _load_values_file("missing.yaml")

        self.assertIn("Trick-or-treat values file not found", str(context.exception))
        self.assertIn("missing.yaml", str(context.exception))

    def test_load_values_file_invalid_yaml(self):
        """Test that ValueError is raised for invalid YAML syntax."""
        mock_file = mock_open(read_data="invalid: yaml: syntax:")

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_values_file("invalid.yaml")

        self.assertIn("Invalid YAML syntax", str(context.exception))

    def test_load_values_file_missing_sections(self):
        """Test that KeyError is raised when required sections are missing."""
        incomplete_data = {"ingot_ranges": {"low_min": 100, "low_max": 500}}
        yaml_content = yaml.dump(incomplete_data)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(KeyError) as context:
                _load_values_file("incomplete.yaml")

        error_msg = str(context.exception)
        self.assertIn("Missing required sections", error_msg)

    def test_load_values_file_missing_ingot_range_fields(self):
        """Test that KeyError is raised when ingot_ranges fields are missing."""
        incomplete_data = {
            "ingot_ranges": {"low_min": 100},
            "jackpot_value": 10000,
            "backrooms": self.valid_values["backrooms"],
            "quiz_master": self.valid_values["quiz_master"],
        }
        yaml_content = yaml.dump(incomplete_data)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(KeyError) as context:
                _load_values_file("incomplete.yaml")

        error_msg = str(context.exception)
        self.assertIn("Missing required ingot_ranges fields", error_msg)

    def test_load_values_file_invalid_ingot_value(self):
        """Test that ValueError is raised for invalid ingot range values."""
        invalid_data = self.valid_values.copy()
        invalid_data["ingot_ranges"] = {
            "low_min": -100,
            "low_max": 500,
            "high_min": 600,
            "high_max": 1000,
        }
        yaml_content = yaml.dump(invalid_data)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_values_file("invalid.yaml")

        self.assertIn("must be a positive integer", str(context.exception))

    def test_load_values_file_invalid_range_order(self):
        """Test that ValueError is raised when min >= max."""
        invalid_data = self.valid_values.copy()
        invalid_data["ingot_ranges"]["low_min"] = 600
        invalid_data["ingot_ranges"]["low_max"] = 500
        yaml_content = yaml.dump(invalid_data)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_values_file("invalid.yaml")

        self.assertIn("must be <", str(context.exception))

    def test_load_values_file_unexpected_error(self):
        """Test that RuntimeError is raised for unexpected errors."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(RuntimeError) as context:
                _load_values_file("test.yaml")

        self.assertIn(
            "Unexpected error loading trick-or-treat values", str(context.exception)
        )


class TestLoadWeightsFile(unittest.TestCase):
    """Test cases for the _load_weights_file function."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_weights = {
            "GIF": 331,
            "REMOVE_INGOTS_LOW": 115,
            "REMOVE_INGOTS_HIGH": 113,
            "ADD_INGOTS_LOW": 109,
            "ADD_INGOTS_HIGH": 104,
            "QUIZ_MASTER": 87,
            "DOUBLE_OR_NOTHING": 53,
            "STEAL": 33,
            "JOKE": 27,
            "BACKROOMS": 13,
            "REMOVE_ALL_INGOTS_TRICK": 12,
            "JACKPOT_INGOTS": 3,
        }

    def test_load_weights_file_success(self):
        """Test successfully loading a valid weights file."""
        yaml_content = yaml.dump(self.valid_weights)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            result = _load_weights_file("test_weights.yaml")

        self.assertEqual(result, self.valid_weights)
        mock_file.assert_called_once_with("test_weights.yaml")

    def test_load_weights_file_not_found(self):
        """Test that FileNotFoundError is raised when file doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError("test.yaml")):
            with self.assertRaises(FileNotFoundError) as context:
                _load_weights_file("missing.yaml")

        self.assertIn("Trick-or-treat weights file not found", str(context.exception))
        self.assertIn("missing.yaml", str(context.exception))

    def test_load_weights_file_invalid_yaml(self):
        """Test that ValueError is raised for invalid YAML syntax."""
        mock_file = mock_open(read_data="invalid: yaml: syntax:")

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_weights_file("invalid.yaml")

        self.assertIn("Invalid YAML syntax", str(context.exception))

    def test_load_weights_file_missing_outcomes(self):
        """Test that ValueError is raised when required outcomes are missing."""
        incomplete_weights = {"GIF": 500, "JOKE": 500}
        yaml_content = yaml.dump(incomplete_weights)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_weights_file("incomplete.yaml")

        error_msg = str(context.exception)
        self.assertIn("Missing required outcomes", error_msg)

    def test_load_weights_file_non_integer_weight(self):
        """Test that TypeError is raised for non-integer weights."""
        invalid_weights = self.valid_weights.copy()
        invalid_weights["GIF"] = "not_an_int"
        yaml_content = yaml.dump(invalid_weights)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(TypeError) as context:
                _load_weights_file("invalid.yaml")

        self.assertIn("must be integers", str(context.exception))

    def test_load_weights_file_negative_weight(self):
        """Test that ValueError is raised for negative or zero weights."""
        invalid_weights = self.valid_weights.copy()
        invalid_weights["GIF"] = -10
        yaml_content = yaml.dump(invalid_weights)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_weights_file("invalid.yaml")

        self.assertIn("must be positive", str(context.exception))

    def test_load_weights_file_duplicate_weights(self):
        """Test that ValueError is raised for duplicate weight values."""
        invalid_weights = self.valid_weights.copy()
        invalid_weights["GIF"] = 100
        invalid_weights["JOKE"] = 100
        yaml_content = yaml.dump(invalid_weights)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_weights_file("invalid.yaml")

        self.assertIn("Duplicate weight values", str(context.exception))

    def test_load_weights_file_wrong_total(self):
        """Test that ValueError is raised when total weight is not 1000."""
        invalid_weights = {
            "GIF": 331,
            "REMOVE_INGOTS_LOW": 115,
            "REMOVE_INGOTS_HIGH": 113,
            "ADD_INGOTS_LOW": 109,
            "ADD_INGOTS_HIGH": 104,
            "QUIZ_MASTER": 87,
            "DOUBLE_OR_NOTHING": 53,
            "STEAL": 33,
            "JOKE": 27,
            "BACKROOMS": 13,
            "REMOVE_ALL_INGOTS_TRICK": 12,
            "JACKPOT_INGOTS": 100,
        }
        yaml_content = yaml.dump(invalid_weights)
        mock_file = mock_open(read_data=yaml_content)

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                _load_weights_file("invalid.yaml")

        error_msg = str(context.exception)
        self.assertIn("Total weight must be 1000", error_msg)
        self.assertIn("but got 1097", error_msg)

    def test_load_weights_file_unexpected_error(self):
        """Test that RuntimeError is raised for unexpected errors."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(RuntimeError) as context:
                _load_weights_file("test.yaml")

        self.assertIn(
            "Unexpected error loading trick-or-treat weights", str(context.exception)
        )
