import unittest
from unittest.mock import patch

from ironforgedbot.commands.ingots.update_ingots import update_ingots
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestUpdateIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.update_ingots.STORAGE")
    @patch("ironforgedbot.commands.ingots.update_ingots.validate_protected_request")
    async def test_update_ingots(self, mock_validate_protected_request, mock_storage):
        """Test that ingots can be written for a player."""
        interaction = create_mock_discord_interaction()

        leader_name = "leader"
        playername = "johnnycache"
        player_id = 123456

        mock_validate_protected_request.return_value = (
            create_test_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        mock_storage.read_member.return_value = Member(
            id=player_id, runescape_name=playername, ingots=10000
        )

        await update_ingots(interaction, playername, 4000)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=player_id, runescape_name=playername, ingots=4000)],
            leader_name,
            note="None",
        )

        interaction.followup.send.assert_called_once_with(
            f"Set ingot count to 4,000 for {playername}. Reason: None "
        )

    @patch("ironforgedbot.commands.ingots.update_ingots.STORAGE")
    @patch("ironforgedbot.commands.ingots.update_ingots.validate_protected_request")
    async def test_update_ingots_player_not_found(
        self, mock_validate_protected_request, mock_storage
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

        await update_ingots(interaction, playername, 400)

        interaction.followup.send.assert_called_once_with(f"{playername} wasn't found.")
