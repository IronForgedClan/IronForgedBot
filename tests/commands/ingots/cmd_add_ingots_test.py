import unittest
from unittest.mock import AsyncMock, patch

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
    from ironforgedbot.commands.ingots.cmd_add_ingots import cmd_add_ingots


class TestAddIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.cmd_add_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_ingots.STORAGE", new_callable=AsyncMock
    )
    async def test_add_ingots(self, mock_storage, mock_validate_playername):
        """Test that ingots can be added to a user."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)

        playername = "johnnycache"
        player_id = 123456

        mock_storage.read_member.return_value = Member(
            id=player_id, runescape_name=playername, ingots=5000
        )
        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_ingots(interaction, playername, 5000)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=player_id, runescape_name=playername, ingots=10000)],
            caller.display_name,
            note="None",
        )

        interaction.followup.send.assert_called_once_with(
            f"\nAdded `5,000` ingots to `{playername}`; reason: None. They now have 10,000 ingots ."
        )

    @patch("ironforgedbot.commands.ingots.cmd_add_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_ingots.STORAGE", new_callable=AsyncMock
    )
    @patch("ironforgedbot.commands.ingots.cmd_add_ingots.send_error_response")
    async def test_addingots_player_not_found(
        self, mock_send_error_response, mock_storage, mock_validate_playername
    ):
        """Test that a missing player is surfaced to caller."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)
        playername = "johnnycache"

        mock_storage.read_member.return_value = None
        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_ingots(interaction, playername, 5)

        mock_send_error_response.assert_awaited_with(
            interaction, f"Member '{playername}' not found in storage."
        )
