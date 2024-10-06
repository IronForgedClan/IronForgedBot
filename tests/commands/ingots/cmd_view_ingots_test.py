import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.ingots.cmd_view_ingots import cmd_view_ingots
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestViewIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_view_ingots.STORAGE", new_callable=AsyncMock
    )
    async def test_ingots(self, mock_storage, mock_validate_playername):
        """Test that a player's ingot total is returned to user."""
        interaction = create_mock_discord_interaction()
        user = create_test_member("johnnycache", ROLES.MEMBER)

        mock_storage.read_member.return_value = Member(
            id=user.id, runescape_name=user.display_name, ingots=2000
        )
        mock_validate_playername.side_effect = lambda _, name: (
            create_test_member(name, ROLES.MEMBER),
            name,
        )

        await cmd_view_ingots(interaction, user.display_name)

        interaction.followup.send.assert_called_once_with(
            f"{user.display_name} has 2,000 ingots "
        )

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_view_ingots.STORAGE", new_callable=AsyncMock
    )
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.send_error_response")
    async def test_ingots_user_not_in_spreadsheet(
        self, mock_send_error_response, mock_storage, mock_validate_playername
    ):
        """Test that a missing player shows error message."""
        interaction = create_mock_discord_interaction()
        player = "johnnycache"

        mock_storage.read_member.return_value = None
        mock_validate_playername.side_effect = lambda _, name: (
            create_test_member(name, ROLES.MEMBER),
            name,
        )

        await cmd_view_ingots(interaction, player)

        mock_send_error_response.assert_awaited_with(
            interaction, f"Member '{player}' not found in storage."
        )
