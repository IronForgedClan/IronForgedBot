import unittest
from unittest.mock import AsyncMock, mock_open, patch

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
    from ironforgedbot.commands.ingots.cmd_add_ingots_bulk import cmd_add_ingots_bulk


class TestAddIngotsBulk(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.cmd_add_ingots_bulk.validate_playername")
    @patch("builtins.open", new_callable=mock_open)
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_ingots_bulk.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_addingots_bulk(
        self, mock_storage, mock_open, mock_validate_playername
    ):
        """Test that ingots can be added to multiple users."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)

        player1 = "johnnycache"
        player1_id = 123456
        player2 = "kennylogs"
        player2_id = 654321

        mock_storage.read_members.return_value = [
            Member(id=player1_id, runescape_name=player1, ingots=5000),
            Member(id=player2_id, runescape_name=player2, ingots=400),
        ]

        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_ingots_bulk(interaction, f"{player1},{player2}", 5000)

        mock_storage.update_members.assert_called_once_with(
            [
                Member(id=player1_id, runescape_name=player1, ingots=10000),
                Member(id=player2_id, runescape_name=player2, ingots=5400),
            ],
            caller.display_name,
            note="None",
        )

        mock_open().write.assert_called_once_with(
            f"Added 5,000 ingots to {player1}. They now have 10,000 ingots\nAdded 5,000 ingots to {player2}. They now have 5,400 ingots"
        )

    @patch("ironforgedbot.commands.ingots.cmd_add_ingots_bulk.validate_playername")
    @patch("builtins.open", new_callable=mock_open)
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_ingots_bulk.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_addingots_bulk_whitespace_stripped(
        self, mock_storage, mock_open, mock_validate_playername
    ):
        """Test that ingots can be added to multiple users."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)

        mock_storage.read_members.return_value = [
            Member(id=123456, runescape_name="johnnycache", ingots=5000),
            Member(id=654321, runescape_name="kennylogs", ingots=400),
        ]

        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_ingots_bulk(interaction, "johnnycache, skagul tosti", 5000)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=123456, runescape_name="johnnycache", ingots=10000)],
            caller.display_name,
            note="None",
        )

        mock_open().write.assert_called_once_with(
            """Added 5,000 ingots to johnnycache. They now have 10,000 ingots
skagul tosti not found in storage."""
        )

    @patch(
        "ironforgedbot.commands.ingots.cmd_add_ingots_bulk.STORAGE",
        new_callable=AsyncMock,
    )
    @patch("ironforgedbot.commands.ingots.cmd_add_ingots_bulk.send_error_response")
    async def test_addingots_bulk_player_fail_validation(
        self, mock_send_error_response, mock_storage
    ):
        """Test that a missing player is surfaced to caller."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        interaction = create_mock_discord_interaction(user=caller)
        bad_name = "somesuperlongfakename"

        mock_storage.read_member.return_value = None

        await cmd_add_ingots_bulk(interaction, bad_name, 5)

        mock_send_error_response.assert_awaited_with(
            interaction, "RSN can only be 1-12 characters long"
        )
