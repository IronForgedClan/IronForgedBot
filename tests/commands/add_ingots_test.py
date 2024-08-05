import unittest
from unittest.mock import patch

from ironforgedbot.commands.ingots.add_ingots import add_ingots
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestAddIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.add_ingots.STORAGE")
    @patch("ironforgedbot.commands.ingots.add_ingots.validate_protected_request")
    async def test_add_ingots(self, mock_validate_protected_request, mock_storage):
        """Test that ingots can be added to a user."""
        interaction = create_mock_discord_interaction()

        leader_name = "leader"
        playername = "johnnycache"
        player_id = 123456

        mock_validate_protected_request.return_value = (
            create_test_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        mock_storage.read_member.return_value = Member(
            id=player_id, runescape_name=playername, ingots=5000
        )

        await add_ingots(interaction, playername, 5000)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=player_id, runescape_name=playername, ingots=10000)],
            leader_name,
            note="None",
        )

        interaction.followup.send.assert_called_once_with(
            f"\nAdded `5,000` ingots to `{playername}`; reason: None. They now have 10,000 ingots ."
        )

    @patch("ironforgedbot.commands.ingots.add_ingots.STORAGE")
    @patch("ironforgedbot.commands.ingots.add_ingots.send_error_response")
    @patch("ironforgedbot.commands.ingots.add_ingots.validate_protected_request")
    async def test_addingots_player_not_found(
        self, mock_validate_protected_request, mock_send_error_response, mock_storage
    ):
        """Test that a missing player is surfaced to caller."""
        interaction = create_mock_discord_interaction()

        leader_name = "leader"
        playername = "johnnycache"

        mock_validate_protected_request.return_value = (
            create_test_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        mock_storage.read_member.return_value = None

        await add_ingots(interaction, playername, 5)

        mock_send_error_response.assert_awaited_with(
            interaction, f"Member '{playername}' not found in spreadsheet"
        )
