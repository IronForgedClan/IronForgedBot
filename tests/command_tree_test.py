import unittest
from unittest.mock import Mock, patch

from ironforgedbot.command_tree import IronForgedCommands
from ironforgedbot.config import ENVIRONMENT


class TestIronForgedCommands(unittest.TestCase):
    def setUp(self):
        self.mock_tree = Mock()
        self.mock_discord_client = Mock()

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_basic_commands_registration(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.PRODUCTION
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 9)
        
        command_names = [call[0][0].name for call in self.mock_tree.add_command.call_args_list]
        expected_commands = ["score", "breakdown", "ingots", "add_remove_ingots", 
                           "roster", "whois", "get_role_members", "raffle", "admin"]
        self.assertEqual(set(command_names), set(expected_commands))

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_trick_or_treat_command_enabled(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = True
        mock_config.ENVIRONMENT = ENVIRONMENT.PRODUCTION
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 10)
        
        command_names = [call[0][0].name for call in self.mock_tree.add_command.call_args_list]
        self.assertIn("trick_or_treat", command_names)

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_debug_commands_development_environment(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.DEVELOPMENT
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 11)
        
        command_names = [call[0][0].name for call in self.mock_tree.add_command.call_args_list]
        self.assertIn("debug_commands", command_names)
        self.assertIn("stress_test", command_names)

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_debug_commands_staging_environment(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.STAGING
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 11)
        
        command_names = [call[0][0].name for call in self.mock_tree.add_command.call_args_list]
        self.assertIn("debug_commands", command_names)
        self.assertIn("stress_test", command_names)

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_all_features_enabled_development(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = True
        mock_config.ENVIRONMENT = ENVIRONMENT.DEVELOPMENT
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        self.assertEqual(self.mock_tree.add_command.call_count, 12)
        
        command_names = [call[0][0].name for call in self.mock_tree.add_command.call_args_list]
        self.assertIn("trick_or_treat", command_names)
        self.assertIn("debug_commands", command_names)
        self.assertIn("stress_test", command_names)

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_command_descriptions(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.PRODUCTION
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        commands = [call[0][0] for call in self.mock_tree.add_command.call_args_list]
        score_command = next(cmd for cmd in commands if cmd.name == "score")
        self.assertEqual(score_command.description, "Displays player score.")
        
        ingots_command = next(cmd for cmd in commands if cmd.name == "ingots")
        self.assertEqual(ingots_command.description, "Displays ingot total.")

    @patch('ironforgedbot.command_tree.CONFIG')
    def test_command_callbacks_assigned(self, mock_config):
        mock_config.TRICK_OR_TREAT_ENABLED = False
        mock_config.ENVIRONMENT = ENVIRONMENT.PRODUCTION
        
        IronForgedCommands(self.mock_tree, self.mock_discord_client)
        
        commands = [call[0][0] for call in self.mock_tree.add_command.call_args_list]
        for command in commands:
            self.assertIsNotNone(command.callback)