import unittest
from unittest.mock import patch

from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)

with patch(
    "ironforgedbot.decorators.require_role",
    mock_require_role,
):
    from ironforgedbot.commands.ingots.cmd_update_ingots import cmd_update_ingots


class TestUpdateIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.cmd_update_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_update_ingots.STORAGE")
    async def test_update_ingots(self, mock_storage, mock_validate_playername):
        """Test that ingots can be written for a player."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)
        player = create_test_member("player", ROLES.MEMBER)

        mock_storage.read_member.return_value = Member(
            id=player.id, runescape_name=player.display_name, ingots=10000
        )
        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_update_ingots(interaction, player.display_name, 4000)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=player.id, runescape_name=player.display_name, ingots=4000)],
            caller.display_name,
            note="None",
        )

        interaction.followup.send.assert_called_once_with(
            f"Set ingot count to 4,000 for {player.display_name}. Reason: None "
        )

    @patch("ironforgedbot.commands.ingots.cmd_update_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_update_ingots.STORAGE")
    async def test_update_ingots_player_not_found(
        self, mock_storage, mock_validate_playername
    ):
        """Test that a missing player is surfaced to caller."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)
        player = create_test_member("player", ROLES.MEMBER)

        mock_storage.read_member.return_value = None
        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_update_ingots(interaction, player.display_name, 400)

        interaction.followup.send.assert_called_once_with(
            f"{player.display_name} wasn't found."
        )
