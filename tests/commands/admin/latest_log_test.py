import unittest
from unittest.mock import MagicMock, patch

from ironforgedbot.commands.admin.latest_log import get_latest_log_file
from ironforgedbot.logging_config import LOG_DIR


class TestLatestLog(unittest.IsolatedAsyncioTestCase):
    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    @patch("discord.File")
    def test_get_latest_log_file(
        self, mock_discord_file, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["log1.txt", "log2.txt", "log3.txt"]

        mock_isfile.side_effect = lambda path: path in {
            f"{LOG_DIR}/log1.txt",
            f"{LOG_DIR}/log2.txt",
            f"{LOG_DIR}/log3.txt",
        }

        mock_getmtime.side_effect = lambda path: {
            "./logs/log1.txt": 100,
            "./logs/log2.txt": 200,
            "./logs/log3.txt": 150,
        }[path]

        mock_discord_file.return_value = MagicMock()

        result = get_latest_log_file()

        mock_discord_file.assert_called_once_with("./logs/log2.txt")
        self.assertIsNotNone(result)

    @patch("os.listdir", return_value=[])
    def test_no_files(self, mock_listdir):
        result = get_latest_log_file()
        self.assertIsNone(result)

    @patch("os.listdir", side_effect=Exception("Error accessing directory"))
    def test_error_handling(self, mock_listdir):
        result = get_latest_log_file()
        self.assertIsNone(result)
