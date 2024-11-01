import unittest
from unittest.mock import AsyncMock, patch

import discord

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
        user = create_test_member("johnnycache", ROLES.MEMBER)
        interaction = create_mock_discord_interaction(user=user)

        mock_storage.read_member.return_value = Member(
            id=user.id, runescape_name=user.display_name, ingots=2000
        )
        mock_validate_playername.side_effect = lambda _, name: (
            user,
            name,
        )

        expected_embed = discord.Embed(title=f" {user.display_name} | Ingots")
        expected_embed.add_field(name="Account ID", value=str(user.id)[:7])
        expected_embed.add_field(name=" Balance", value="2,000")

        await cmd_view_ingots(interaction, user.display_name)

        interaction.followup.send.assert_called_once()
        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        self.assertEqual(actual_embed.title, expected_embed.title)
        self.assertEqual(len(actual_embed.fields), len(expected_embed.fields))

        for expected, actual in zip(expected_embed.fields, actual_embed.fields):
            self.assertEqual(expected.name, actual.name)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.inline, actual.inline)

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
            interaction, f"Member '{player}' could not be found."
        )
