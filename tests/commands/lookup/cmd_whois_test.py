from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import wom

from ironforgedbot.commands.lookup.cmd_whois import cmd_whois
from ironforgedbot.common.roles import ROLE
from tests.helpers import create_mock_discord_interaction, create_test_member

mock_name_change_list = [
    SimpleNamespace(
        **{
            "new_name": "test",
            "old_name": "tester",
            "status": wom.NameChangeStatus.Approved,
            "resolved_at": "123",
        }
    )
]


class WhoisTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois(
        self, mock_validate_playername, mock_wom, mock_relative_time
    ):
        playername = "tester"
        user = create_test_member(playername, ROLE.MEMBER)
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)

        mock_relative_time.return_value = "sometime"

        mock_wom_client = AsyncMock(spec=wom.Client)

        mock_result = MagicMock()

        mock_result.is_err = False
        mock_result.unwrap.return_value = mock_name_change_list

        mock_wom_client.players.get_name_changes = AsyncMock()
        mock_wom_client.players.get_name_changes.return_value = mock_result

        mock_wom.return_value = mock_wom_client

        expected_embed = discord.Embed(title=f"📋 {user.display_name} | Name History")

        expected_embed.add_field(
            name="", value="**sometime**: tester → test", inline=False
        )

        await cmd_whois(interaction, playername)

        interaction.followup.send.assert_called_once()

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        self.assertEqual(actual_embed.title, expected_embed.title)
        self.assertEqual(len(actual_embed.fields), len(expected_embed.fields))

        for expected, actual in zip(expected_embed.fields, actual_embed.fields):
            self.assertEqual(expected.name, actual.name)
            self.assertEqual(expected.value, actual.value)

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_return_error_if_lookup_fails(
        self, mock_validate_playername, mock_wom, mock_send_error_response
    ):
        playername = "tester"
        user = create_test_member(playername, ROLE.MEMBER)
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)

        mock_wom_client = AsyncMock(spec=wom.Client)

        mock_result = MagicMock()
        mock_result.is_err = True

        mock_wom_client.players.get_name_changes = AsyncMock()
        mock_wom_client.players.get_name_changes.return_value = mock_result

        mock_wom_client.close = AsyncMock()

        mock_wom.return_value = mock_wom_client

        await cmd_whois(interaction, playername)

        mock_send_error_response.assert_awaited_once()
