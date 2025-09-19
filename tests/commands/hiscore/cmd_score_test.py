import unittest
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.http import HttpException
from ironforgedbot.models.score import ScoreBreakdown, SkillScore, ActivityScore
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)

with patch("ironforgedbot.decorators.require_role", mock_require_role):
    from ironforgedbot.commands.hiscore.cmd_score import cmd_score


class TestCmdScore(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.prospect_user = create_test_member("ProspectUser", [ROLE.PROSPECT])
        self.interaction = create_mock_discord_interaction(user=self.test_user)
        
        # Sample score data
        self.sample_skills = [
            SkillScore("Attack", None, 1, "Attack", 13034000, 99, 1000),
            SkillScore("Defence", None, 2, "Defence", 6517000, 85, 500),
        ]
        self.sample_bosses = [
            ActivityScore("Zulrah", None, 1, "Zulrah", 200, 100),
        ]
        self.sample_clues = [
            ActivityScore("Beginner", None, 1, "ClueScrolls_Beginner", 100, 50),
        ]
        self.sample_raids = [
            ActivityScore("CoX", None, 1, "CoX", 50, 25),
        ]
        
        self.sample_score_breakdown = ScoreBreakdown(
            self.sample_skills, self.sample_bosses, self.sample_clues, self.sample_raids
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    async def test_cmd_score_success_member(
        self, mock_check_role, mock_find_emoji, mock_get_color, mock_get_rank, 
        mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_check_role.return_value = True
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown
        
        await cmd_score(self.interaction, "TestUser")
        
        mock_validate.assert_called_once_with(self.interaction.guild, "TestUser", must_be_member=False)
        mock_score_service.get_player_score.assert_called_once_with("TestUser")
        self.interaction.followup.send.assert_called_once()
        
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("TestUser", sent_embed.title)
        self.assertIn("Score:", sent_embed.title)
        self.assertEqual(len(sent_embed.fields), 3)  # Skill Points, Activity Points, Rank Progress

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    async def test_cmd_score_default_player_self(
        self, mock_check_role, mock_find_emoji, mock_get_color, mock_get_rank,
        mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_check_role.return_value = True
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown
        
        await cmd_score(self.interaction, None)  # No player specified
        
        mock_validate.assert_called_once_with(self.interaction.guild, "TestUser", must_be_member=False)

    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_validation_error(self, mock_validate, mock_send_error):
        mock_validate.side_effect = Exception("Invalid player name")
        
        await cmd_score(self.interaction, "BadName")
        
        mock_send_error.assert_called_once_with(self.interaction, "Invalid player name")

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    async def test_cmd_score_hiscores_error(
        self, mock_send_error, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresError("API Error")
        
        await cmd_score(self.interaction, "TestUser")
        
        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again."
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    async def test_cmd_score_http_exception(
        self, mock_send_error, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HttpException("Network Error")
        
        await cmd_score(self.interaction, "TestUser")
        
        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again."
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_member_no_hiscore_values")
    async def test_cmd_score_member_no_hiscores(
        self, mock_send_no_hiscore, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresNotFound("No hiscores found")
        
        await cmd_score(self.interaction, "TestUser")
        
        mock_send_no_hiscore.assert_called_once_with(self.interaction, "TestUser")

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_not_clan_member")
    async def test_cmd_score_non_member_hiscores_not_found(
        self, mock_send_not_clan, mock_find_emoji, mock_get_color, mock_get_rank,
        mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (None, "NonMember")  # Not a guild member
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresNotFound("No hiscores found")
        
        await cmd_score(self.interaction, "NonMember")
        
        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_prospect_response")
    async def test_cmd_score_prospect_response(
        self, mock_send_prospect, mock_check_role, mock_find_emoji, mock_get_color,
        mock_get_rank, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.prospect_user, "ProspectUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_check_role.return_value = True  # Is prospect
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown
        
        await cmd_score(self.interaction, "ProspectUser")
        
        mock_send_prospect.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_not_clan_member")
    async def test_cmd_score_not_clan_member_response(
        self, mock_send_not_clan, mock_check_role, mock_find_emoji, mock_get_color,
        mock_get_rank, mock_validate, mock_http, mock_score_service_class
    ):
        non_member = create_test_member("NonMember", [])  # No roles
        mock_validate.return_value = (non_member, "NonMember")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_check_role.side_effect = lambda member, role: role != ROLE.MEMBER  # Not a member
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown
        
        await cmd_score(self.interaction, "NonMember")
        
        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_god_alignment_from_member")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    async def test_cmd_score_god_rank_saradomin(
        self, mock_check_role, mock_find_emoji, mock_get_god_alignment, mock_get_color,
        mock_get_rank, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.GOD
        mock_get_color.return_value = discord.Color.blue()
        mock_get_god_alignment.return_value = GOD_ALIGNMENT.SARADOMIN
        mock_find_emoji.side_effect = lambda x: f":{x}:"
        mock_check_role.return_value = True
        
        # High points to trigger GOD rank
        high_score_breakdown = ScoreBreakdown(
            [SkillScore("Attack", None, 1, "Attack", 200000000, 99, 50000)], [], [], []
        )
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = high_score_breakdown
        
        await cmd_score(self.interaction, "TestUser")
        
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        # Should have god alignment field instead of rank progress
        self.assertEqual(len(sent_embed.fields), 3)  # Skill Points, Activity Points, God Alignment

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    async def test_cmd_score_rank_progress(
        self, mock_render_percentage, mock_check_role, mock_find_emoji, mock_get_next_rank,
        mock_get_color, mock_get_rank, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.side_effect = lambda x: f":{x}:"
        mock_check_role.return_value = True
        mock_render_percentage.return_value = "25%"
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown
        
        await cmd_score(self.interaction, "TestUser")
        
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        rank_progress_field = sent_embed.fields[2]
        self.assertEqual(rank_progress_field.name, "Rank Progress")
        self.assertIn("→", rank_progress_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    async def test_cmd_score_points_calculation(
        self, mock_render_percentage, mock_check_role, mock_find_emoji, mock_get_color,
        mock_get_rank, mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_check_role.return_value = True
        mock_render_percentage.side_effect = lambda part, total: f"{int(part/total*100)}%"
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown
        
        await cmd_score(self.interaction, "TestUser")
        
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        skill_field = sent_embed.fields[0]
        activity_field = sent_embed.fields[1]
        
        # Expected: 1500 skill points, 175 activity points = 1675 total
        self.assertEqual(skill_field.name, "Skill Points")
        self.assertIn("1,500", skill_field.value)
        self.assertEqual(activity_field.name, "Activity Points")
        self.assertIn("175", activity_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    async def test_cmd_score_empty_score_data(
        self, mock_check_role, mock_find_emoji, mock_get_color, mock_get_rank,
        mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_check_role.return_value = True
        
        empty_score_breakdown = ScoreBreakdown([], [], [], [])
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = empty_score_breakdown
        
        await cmd_score(self.interaction, "TestUser")
        
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("Score: 0", sent_embed.title)

    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreService")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.check_member_has_role")
    async def test_cmd_score_large_numbers_formatting(
        self, mock_check_role, mock_find_emoji, mock_get_color, mock_get_rank,
        mock_validate, mock_http, mock_score_service_class
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.ADAMANT
        mock_get_color.return_value = discord.Color.green()
        mock_find_emoji.return_value = ":adamant:"
        mock_check_role.return_value = True
        
        large_score_breakdown = ScoreBreakdown(
            [SkillScore("Attack", None, 1, "Attack", 200000000, 99, 1_000_000)], 
            [ActivityScore("Zulrah", None, 1, "Zulrah", 10000, 500_000)], 
            [], []
        )
        
        mock_score_service = AsyncMock()
        mock_score_service_class.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = large_score_breakdown
        
        await cmd_score(self.interaction, "TestUser")
        
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("1,500,000", sent_embed.title)  # Total score with commas