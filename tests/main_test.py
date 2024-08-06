import unittest
from unittest.mock import MagicMock, patch

from ironforgedbot.client import DiscordClient
import main


class TestMain(unittest.IsolatedAsyncioTestCase):
    @patch("main.IronForgedCommands")
    @patch("main.discord.app_commands.CommandTree")
    @patch("main.DiscordClient", spec=True)
    def test_create_client(self, mock_client, mock_tree, mock_commands):
        result = main.create_client(MagicMock(), MagicMock(), MagicMock())

        mock_client.assert_called_once()
        mock_tree.assert_called_once()
        mock_commands.assert_called_once()

        self.assertIsInstance(result, DiscordClient)

    def test_create_discord_intents(self):
        result = main.create_discord_intents()

        self.assertEqual(result.members, True)

    @patch("sys.argv", ["main.py", "--upload"])
    def test_parse_cli_arguments_upload_true(self):
        result = main.parse_cli_arguments()

        self.assertEqual(result.upload, True)

    @patch("sys.argv", ["main.py"])
    def test_parse_cli_arguments_upload_false(self):
        result = main.parse_cli_arguments()

        self.assertEqual(result.upload, False)

    @patch("main.os.makedirs")
    def test_create_temp_dir(self, mock_makedirs):
        dir = "./test"

        main.create_temp_dir(dir)

        mock_makedirs.assert_called_once_with(dir, exist_ok=True)

    @patch("main.os.makedirs")
    @patch("main.logging")
    @patch("main.sys.exit")
    def test_create_temp_dir_permission_error(
        self, mock_exit, mock_logging, mock_makedirs
    ):
        dir = "./test"
        mock_makedirs.side_effect = PermissionError

        main.create_temp_dir(dir)

        mock_logging.critical.assert_called_once_with(
            f"Unable to create temp directory: {dir}"
        )

        mock_exit.assert_called_once_with(1)
