import unittest
from unittest.mock import patch

from ironforgedbot.commands.ingots.view_ingots import view_ingots
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestViewIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.view_ingots.STORAGE")
    @patch("ironforgedbot.commands.ingots.view_ingots.validate_user_request")
    async def test_ingots(self, mock_validate_user_request, mock_storage):
        """Test that a player's ingot total is returned to user."""
        interaction = create_mock_discord_interaction()
        user = create_test_member("johnnycache", ROLES.MEMBER)

        mock_validate_user_request.return_value = (
            user,
            user.display_name,
        )

        mock_storage.read_member.return_value = Member(
            id=user.id, runescape_name=user.display_name, ingots=2000
        )

        await view_ingots(interaction, user.display_name)

        interaction.followup.send.assert_called_once_with(
            f"{user.display_name} has 2,000 ingots "
        )

    @patch("ironforgedbot.commands.ingots.view_ingots.STORAGE")
    @patch("ironforgedbot.commands.ingots.view_ingots.send_error_response")
    @patch("ironforgedbot.commands.ingots.view_ingots.validate_user_request")
    async def test_ingots_user_not_in_spreadsheet(
        self, mock_validate_user_request, mock_send_error_response, mock_storage
    ):
        """Test that a missing player shows error message."""
        interaction = create_mock_discord_interaction()
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            create_test_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage.read_member.return_value = None

        await view_ingots(interaction, player)

        mock_send_error_response.assert_awaited_with(
            interaction, f"Member '{player}' not found in storage."
        )
