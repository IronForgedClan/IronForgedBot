import os
import tempfile
import unittest
from unittest.mock import mock_open, patch


class TestGetApiVersion(unittest.TestCase):
    def test_reads_from_file(self):
        from api.version import get_api_version

        with patch(
            "builtins.open",
            mock_open(read_data='{"bot": "0.0.0", "api": "1.2.3"}'),
        ) as mock_file:
            result = get_api_version()
            self.assertEqual(result, "1.2.3")
            mock_file.assert_called_once()

    def test_returns_api_field_value(self):
        from api.version import get_api_version

        with patch(
            "builtins.open",
            mock_open(read_data='{"bot": "0.0.0", "api": "  0.1.0  "}'),
        ):
            result = get_api_version()
            self.assertEqual(result, "  0.1.0  ")

    def test_reads_actual_version_file(self):
        from api.version import get_api_version

        result = get_api_version()
        self.assertTrue(len(result) > 0)
        self.assertNotIn("\n", result)
        self.assertNotIn(" ", result)

    def test_missing_file_raises(self):
        from api.version import get_api_version

        with patch("api.version.open", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                get_api_version()
