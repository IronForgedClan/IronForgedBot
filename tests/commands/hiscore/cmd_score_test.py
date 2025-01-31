import unittest
from unittest.mock import patch

import discord

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)

from tests.helpers import mock_score_breakdown

with patch(
    "ironforgedbot.decorators.require_role",
    mock_require_role,
):
    from ironforgedbot.commands.hiscore.cmd_score import cmd_score


class ScoreTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.score_info")
    async def test_cmd_score(self, mock_score_info, mock_validate_playername):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)

        mock_score_info.return_value = mock_score_breakdown

        expected_embed = discord.Embed(title=f" {user.display_name} | Score: 40")
        expected_embed.add_field(name="Skill Points", value="18 (45%)", inline=True)
        expected_embed.add_field(name="Activity Points", value="22 (55%)", inline=True)
        expected_embed.add_field(
            name="Rank Progress",
            value=" →  40/700 (6%)",
            inline=False,
        )

        await cmd_score(interaction, playername)

        interaction.followup.send.assert_called_once()

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        self.assertEqual(actual_embed.title, expected_embed.title)
        self.assertEqual(len(actual_embed.fields), len(expected_embed.fields))

        for expected, actual in zip(expected_embed.fields, actual_embed.fields):
            self.assertEqual(expected.name, actual.name)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.inline, actual.inline)

    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.score_info")
    async def test_cmd_score_god_alignment(
        self, mock_score_info, mock_validate_playername
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)

        mock_score_breakdown.skills[0]["points"] = 20_000
        mock_score_info.return_value = mock_score_breakdown

        expected_embed = discord.Embed(title=f" {user.display_name} | Score: 20,022")
        expected_embed.add_field(
            name="Skill Points", value="20,000 (>99%)", inline=True
        )
        expected_embed.add_field(name="Activity Points", value="22 (<1%)", inline=True)
        # NOTE: custom emojis won't be rendered in tests
        expected_embed.add_field(
            name="",
            value=":nerd::nerd::nerd::nerd:",
            inline=False,
        )

        await cmd_score(interaction, playername)

        interaction.followup.send.assert_called_once()

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        self.assertEqual(actual_embed.title, expected_embed.title)
        self.assertEqual(len(actual_embed.fields), len(expected_embed.fields))

        for expected, actual in zip(expected_embed.fields, actual_embed.fields):
            self.assertEqual(expected.name, actual.name)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.inline, actual.inline)

    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_fail_if_validate_playername_raises(
        self, mock_validate_playername, mock_send_error_response
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.side_effect = Exception()

        await cmd_score(interaction, playername)

        mock_send_error_response.assert_awaited_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_fail_if_score_info_raises(
        self, mock_validate_playername, mock_send_error_response, mock_score_info
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.side_effect = lambda _, name: (user, name)
        mock_score_info.side_effect = RuntimeError()

        await cmd_score(interaction, playername)

        mock_send_error_response.assert_awaited_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_prospect_response")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_prospect_response(
        self,
        mock_validate_playername,
        mock_send_prospect_response,
        mock_score_info,
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.PROSPECT])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)
        mock_score_info.return_value = mock_score_breakdown

        await cmd_score(interaction, playername)

        mock_send_prospect_response.assert_awaited_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_member_no_hiscore_values")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_member_no_hiscore_response(
        self,
        mock_validate_playername,
        mock_send_no_hiscore_values,
        mock_score_info,
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)
        mock_score_info.return_value = None

        await cmd_score(interaction, playername)

        mock_send_no_hiscore_values.assert_awaited_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_not_clan_member")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_not_in_clan_response(
        self,
        mock_validate_playername,
        mock_send_not_clan_member,
        mock_score_info,
    ):
        playername = "tester"
        interaction = create_mock_discord_interaction()

        mock_validate_playername.return_value = (None, playername)
        mock_score_info.return_value = mock_score_breakdown

        await cmd_score(interaction, playername)

        mock_send_not_clan_member.assert_awaited_once()
