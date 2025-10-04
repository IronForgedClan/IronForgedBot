import unittest
from unittest.mock import MagicMock, Mock, patch

import discord

from ironforgedbot.client import DiscordClient
import main


class MainTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_intents = Mock(spec=discord.Intents)
        self.test_guild_id = 123456789

    @patch("main.IronForgedCommands")
    @patch("main.IronForgedCommandTree")
    @patch("main.DiscordClient")
    @patch("main.discord.Object")
    def test_create_client_success(
        self, mock_object, mock_client, mock_tree, mock_commands
    ):
        mock_guild = Mock()
        mock_object.return_value = mock_guild
        mock_client_instance = Mock(spec=DiscordClient)
        mock_client.return_value = mock_client_instance
        mock_tree_instance = Mock()
        mock_tree.return_value = mock_tree_instance

        result = main.create_client(self.mock_intents, True, self.test_guild_id)

        mock_object.assert_called_once_with(id=self.test_guild_id)
        mock_client.assert_called_once_with(
            intents=self.mock_intents, upload=True, guild=mock_guild
        )
        mock_tree.assert_called_once_with(mock_client_instance)
        mock_commands.assert_called_once_with(mock_tree_instance, mock_client_instance)
        self.assertEqual(mock_client_instance.tree, mock_tree_instance)
        self.assertEqual(result, mock_client_instance)

    def test_create_discord_intents_sets_members_true(self):
        result = main.create_discord_intents()

        self.assertIsInstance(result, discord.Intents)
        self.assertTrue(result.members)

    @patch("main.os.makedirs")
    def test_create_temp_dir_success(self, mock_makedirs):
        test_dir = "./temp_test"

        main.create_temp_dir(test_dir)

        mock_makedirs.assert_called_once_with(test_dir, exist_ok=True)

    @patch("main.sys.exit")
    @patch("main.logging.critical")
    @patch("main.os.makedirs")
    def test_create_temp_dir_handles_permission_error(
        self, mock_makedirs, mock_critical, mock_exit
    ):
        test_dir = "./restricted_test"
        mock_makedirs.side_effect = PermissionError("Access denied")

        main.create_temp_dir(test_dir)

        mock_makedirs.assert_called_once_with(test_dir, exist_ok=True)
        mock_critical.assert_called_once_with(
            f"Unable to create temp directory: {test_dir}"
        )
        mock_exit.assert_called_once_with(1)

    @patch("main.sys.exit")
    @patch("main.logging.critical")
    @patch("main.os.makedirs")
    def test_create_temp_dir_handles_generic_exception(
        self, mock_makedirs, mock_critical, mock_exit
    ):
        test_dir = "./error_test"
        mock_makedirs.side_effect = OSError("Disk full")

        main.create_temp_dir(test_dir)

        mock_makedirs.assert_called_once_with(test_dir, exist_ok=True)
        mock_critical.assert_called_once_with(
            f"Unable to create temp directory: {test_dir}"
        )
        mock_exit.assert_called_once_with(1)

    @patch("main.create_client")
    @patch("main.create_discord_intents")
    @patch("main.create_temp_dir")
    @patch("main.CONFIG")
    @patch("main.STATE")
    @patch("main.HTTP")
    @patch("main.BOSSES")
    @patch("main.CLUES")
    @patch("main.RAIDS")
    @patch("main.SKILLS")
    def test_init_bot_initializes_all_components(
        self,
        mock_skills,
        mock_raids,
        mock_clues,
        mock_bosses,
        mock_http,
        mock_state,
        mock_config,
        mock_create_temp,
        mock_create_intents,
        mock_create_client,
    ):
        mock_config.TEMP_DIR = "./temp"
        mock_config.GUILD_ID = self.test_guild_id
        mock_config.BOT_VERSION = "1.0.0"
        mock_config.BOT_TOKEN = "test_token"
        mock_intents = Mock()
        mock_create_intents.return_value = mock_intents
        mock_client = Mock()
        mock_client.run = Mock()
        mock_create_client.return_value = mock_client

        main.init_bot()

        mock_create_temp.assert_called_once_with("./temp")
        mock_create_intents.assert_called_once()
        mock_create_client.assert_called_once_with(
            mock_intents, upload=True, guild_id=self.test_guild_id
        )
        mock_client.run.assert_called_once_with("test_token")

    @patch("main.create_client")
    @patch("main.create_discord_intents")
    @patch("main.create_temp_dir")
    @patch("main.CONFIG")
    def test_init_bot_handles_missing_dependencies(
        self, mock_config, mock_create_temp, mock_create_intents, mock_create_client
    ):
        mock_config.TEMP_DIR = "./temp"
        mock_config.GUILD_ID = self.test_guild_id
        mock_config.BOT_VERSION = "1.0.0"
        mock_config.BOT_TOKEN = "test_token"

        with patch("main.STATE", None), patch("main.HTTP", Mock()), patch(
            "main.BOSSES", Mock()
        ), patch("main.CLUES", Mock()), patch("main.RAIDS", Mock()), patch(
            "main.SKILLS", Mock()
        ):

            mock_intents = Mock()
            mock_create_intents.return_value = mock_intents
            mock_client = Mock()
            mock_client.run = Mock()
            mock_create_client.return_value = mock_client

            main.init_bot()

            mock_create_temp.assert_called_once_with("./temp")
            mock_create_intents.assert_called_once()
            mock_create_client.assert_called_once_with(
                mock_intents, upload=True, guild_id=self.test_guild_id
            )
            mock_client.run.assert_called_once_with("test_token")
