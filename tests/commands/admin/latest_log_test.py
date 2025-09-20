import unittest
from unittest.mock import Mock, patch

from ironforgedbot.commands.admin.latest_log import get_latest_log_file
from ironforgedbot.logging_config import LOG_DIR


class TestLatestLog(unittest.TestCase):
    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    @patch("discord.File")
    def test_get_latest_log_file_success(
        self, mock_discord_file, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["log1.txt", "log2.txt", "log3.txt"]
        mock_isfile.return_value = True
        mock_getmtime.side_effect = lambda path: {
            "./logs/log1.txt": 100,
            "./logs/log2.txt": 200,
            "./logs/log3.txt": 150,
        }[path]
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        result = get_latest_log_file()

        mock_discord_file.assert_called_once_with("./logs/log2.txt")
        self.assertEqual(result, mock_file)

    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    @patch("discord.File")
    def test_get_latest_log_file_mixed_files_and_directories(
        self, mock_discord_file, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["log1.txt", "subdirectory", "log2.txt", "log3.txt"]
        mock_isfile.side_effect = lambda path: path in {
            f"{LOG_DIR}/log1.txt",
            f"{LOG_DIR}/log2.txt",
            f"{LOG_DIR}/log3.txt",
        }
        mock_getmtime.side_effect = lambda path: {
            "./logs/log1.txt": 100,
            "./logs/log2.txt": 300,
            "./logs/log3.txt": 150,
        }[path]
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        result = get_latest_log_file()

        mock_discord_file.assert_called_once_with("./logs/log2.txt")
        self.assertEqual(result, mock_file)

    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    @patch("discord.File")
    def test_get_latest_log_file_single_file(
        self, mock_discord_file, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["single_log.txt"]
        mock_isfile.return_value = True
        mock_getmtime.return_value = 123456789
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        result = get_latest_log_file()

        mock_discord_file.assert_called_once_with("./logs/single_log.txt")
        self.assertEqual(result, mock_file)

    @patch("os.listdir", return_value=[])
    def test_get_latest_log_file_empty_directory(self, mock_listdir):
        result = get_latest_log_file()
        self.assertIsNone(result)

    @patch("os.listdir")
    @patch("os.path.isfile", return_value=False)
    def test_get_latest_log_file_no_files_only_directories(
        self, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["dir1", "dir2", "dir3"]

        result = get_latest_log_file()

        self.assertIsNone(result)

    @patch("os.listdir", side_effect=OSError("Permission denied"))
    @patch("ironforgedbot.commands.admin.latest_log.logger")
    def test_get_latest_log_file_listdir_error(self, mock_logger, mock_listdir):
        result = get_latest_log_file()

        self.assertIsNone(result)
        mock_logger.error.assert_called_once()

    @patch("os.listdir")
    @patch("os.path.isfile", side_effect=OSError("File access error"))
    @patch("ironforgedbot.commands.admin.latest_log.logger")
    def test_get_latest_log_file_isfile_error(
        self, mock_logger, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["log1.txt"]

        result = get_latest_log_file()

        self.assertIsNone(result)
        mock_logger.error.assert_called_once()

    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime", side_effect=OSError("File modification time error"))
    @patch("ironforgedbot.commands.admin.latest_log.logger")
    def test_get_latest_log_file_getmtime_error(
        self, mock_logger, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["log1.txt"]
        mock_isfile.return_value = True

        result = get_latest_log_file()

        self.assertIsNone(result)
        mock_logger.error.assert_called_once()

    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    @patch("discord.File", side_effect=Exception("Discord file creation error"))
    @patch("ironforgedbot.commands.admin.latest_log.logger")
    def test_get_latest_log_file_discord_file_error(
        self, mock_logger, mock_discord_file, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["log1.txt"]
        mock_isfile.return_value = True
        mock_getmtime.return_value = 123456789

        result = get_latest_log_file()

        self.assertIsNone(result)
        mock_logger.error.assert_called_once()

    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    @patch("discord.File")
    def test_get_latest_log_file_path_construction(
        self, mock_discord_file, mock_getmtime, mock_isfile, mock_listdir
    ):
        mock_listdir.return_value = ["test.log"]
        mock_isfile.return_value = True
        mock_getmtime.return_value = 123456789
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        result = get_latest_log_file()

        expected_path = f"{LOG_DIR}/test.log"
        mock_discord_file.assert_called_once_with(expected_path)
        self.assertEqual(result, mock_file)
