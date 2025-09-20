import unittest
from unittest.mock import Mock, AsyncMock, patch

import discord

from ironforgedbot.command_tree import IronForgedCommandTree, IronForgedCommands
from ironforgedbot.config import ENVIRONMENT


class TestIronForgedCommandTree(unittest.IsolatedAsyncioTestCase):
    @patch('ironforgedbot.command_tree.send_error_response')
    @patch('ironforgedbot.command_tree.logger')
    async def test_on_error_check_failure(self, mock_logger, mock_send_error):
        tree = IronForgedCommandTree.__new__(IronForgedCommandTree)
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.response = AsyncMock()
        mock_interaction.response.defer = AsyncMock()
        
        error = discord.app_commands.CheckFailure("Permission denied")
        
        await tree.on_error(mock_interaction, error)
        
        mock_logger.info.assert_called_once_with(error)
        mock_interaction.response.defer.assert_called_once_with(thinking=True, ephemeral=True)
        mock_send_error.assert_called_once_with(
            mock_interaction,
            "You do not have permission to run that command."
        )

    @patch('ironforgedbot.command_tree.send_error_response')
    @patch('ironforgedbot.command_tree.logger')
    async def test_on_error_general_error(self, mock_logger, mock_send_error):
        tree = IronForgedCommandTree.__new__(IronForgedCommandTree)
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.response = AsyncMock()
        
        error = Exception("Something went wrong")
        
        await tree.on_error(mock_interaction, error)
        
        mock_logger.critical.assert_called_once()
        mock_send_error.assert_called_once()
        args = mock_send_error.call_args[0]
        self.assertEqual(args[0], mock_interaction)
        self.assertIn("An unhandled error has occurred", args[1])


class TestIronForgedCommands(unittest.TestCase):
    def setUp(self):
        self.mock_tree = Mock()
        self.mock_discord_client = Mock()

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_init_basic_commands(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.PRODUCTION
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 9)

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_init_with_trick_or_treat(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = True
        mock_config.ENVIRONMENT = ENVIRONMENT.PRODUCTION
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 10)

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_init_with_debug_commands(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.DEVELOPMENT
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 11)