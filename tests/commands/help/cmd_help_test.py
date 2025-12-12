import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.common.roles import ROLE
from tests.helpers import create_mock_discord_interaction, mock_require_role

with patch("ironforgedbot.decorators.require_role", mock_require_role):
    from ironforgedbot.commands.help.cmd_help import cmd_help


class TestCmdHelp(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.interaction = create_mock_discord_interaction(
            user=MagicMock(display_name="TestUser")
        )
        self.interaction.client.tree = MagicMock()

    @patch("ironforgedbot.commands.help.cmd_help.ViewMenu")
    @patch("ironforgedbot.commands.help.cmd_help.ViewButton")
    async def test_cmd_help_paginated_output(self, mock_view_button, mock_view_menu):
        mock_cmds = []
        for name, desc in [
            ("score", "View your score"),
            ("breakdown", "Score breakdown"),
            ("ingots", "Check ingots"),
            ("raffle", "Raffle info"),
            ("trick_or_treat", "Halloween fun"),
            ("some_other", "Misc command"),
            ("ignored_command", "Should be ignored"),
        ]:
            cmd = MagicMock()
            cmd.name = name
            cmd.description = desc
            mock_cmds.append(cmd)

        self.interaction.client.tree.get_commands.return_value = mock_cmds

        mock_view_button.back = MagicMock(return_value=MagicMock())
        mock_view_button.next = MagicMock(return_value=MagicMock())

        import sys

        IGNORED_COMMANDS = sys.modules[
            "ironforgedbot.commands.help.cmd_help"
        ].IGNORED_COMMANDS
        if "ignored_command" not in IGNORED_COMMANDS:
            IGNORED_COMMANDS.append("ignored_command")

        mock_menu_instance = MagicMock()
        mock_menu_instance.start = AsyncMock()
        mock_view_menu.return_value = mock_menu_instance

        await cmd_help(self.interaction)

        mock_view_menu.assert_called_once()
        self.assertEqual(mock_menu_instance.add_page.call_count, 1)
        self.assertEqual(mock_menu_instance.add_button.call_count, 2)
        mock_menu_instance.start.assert_awaited_once()

    @patch("ironforgedbot.commands.help.cmd_help.ViewMenu")
    @patch("ironforgedbot.commands.help.cmd_help.ViewButton")
    async def test_cmd_help_empty_command_list(self, mock_view_button, mock_view_menu):
        self.interaction.client.tree.get_commands.return_value = []

        mock_view_button.back = MagicMock(return_value=MagicMock())
        mock_view_button.next = MagicMock(return_value=MagicMock())

        mock_menu_instance = MagicMock()
        mock_menu_instance.start = AsyncMock()
        mock_view_menu.return_value = mock_menu_instance

        await cmd_help(self.interaction)

        mock_menu_instance.start.assert_awaited_once()
