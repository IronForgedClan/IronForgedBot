import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.http import HttpException
from ironforgedbot.models.score import ScoreBreakdown, SkillScore, ActivityScore
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_score_data,
    mock_require_role,
)

with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    with patch("ironforgedbot.common.helpers.find_emoji", return_value="<:emoji:123>"):
        from ironforgedbot.commands.hiscore.cmd_breakdown import cmd_breakdown


class TestCmdBreakdown(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.prospect_user = create_test_member("ProspectUser", [ROLE.PROSPECT])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

        self.sample_score_breakdown = create_test_score_data(
            skills_count=2, activities_count=4
        )

        # Extract individual components for tests that need them
        self.sample_skills = self.sample_score_breakdown.skills
        self.sample_clues = self.sample_score_breakdown.clues
        self.sample_raids = self.sample_score_breakdown.raids
        self.sample_bosses = self.sample_score_breakdown.bosses

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    async def test_cmd_breakdown_validation_error(self, mock_validate, mock_send_error):
        mock_validate.side_effect = Exception("Invalid player name")

        await cmd_breakdown(self.interaction, "BadName")

        mock_send_error.assert_called_once_with(
            self.interaction, "Invalid player name", report_to_channel=False
        )

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_error_response")
    async def test_cmd_breakdown_hiscores_error(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresError("API Error")

        await cmd_breakdown(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_error_response")
    async def test_cmd_breakdown_http_exception(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HttpException("Network Error")

        await cmd_breakdown(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_member_no_hiscore_values")
    async def test_cmd_breakdown_member_no_hiscores(
        self, mock_send_no_hiscore, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresNotFound(
            "No hiscores found"
        )

        await cmd_breakdown(self.interaction, "TestUser")

        mock_send_no_hiscore.assert_called_once_with(self.interaction, "TestUser")

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_not_clan_member")
    async def test_cmd_breakdown_non_member_hiscores_not_found(
        self, mock_send_not_clan, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (None, "NonMember")

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresNotFound(
            "No hiscores found"
        )

        await cmd_breakdown(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.check_member_has_role")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_prospect_response")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    async def test_cmd_breakdown_prospect_response(
        self,
        mock_find_emoji,
        mock_send_prospect,
        mock_check_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.prospect_user, "ProspectUser")
        mock_check_role.return_value = True
        mock_find_emoji.return_value = ":prospect:"

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_breakdown(self.interaction, "ProspectUser")

        mock_send_prospect.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_not_clan_member")
    async def test_cmd_breakdown_not_clan_member_response(
        self, mock_send_not_clan, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (None, "NonMember")

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_breakdown(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_success_regular_rank(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock()
        mock_view_menu.return_value = mock_menu

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
        mock_score_service.get_player_score.assert_called_once_with("TestUser")
        mock_menu.add_page.assert_called()
        mock_menu.add_button.assert_called()
        mock_menu.start.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_god_alignment_from_member")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_success_god_rank(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.GOD
        mock_get_color.return_value = discord.Color.blue()
        mock_get_god_alignment.return_value = GOD_ALIGNMENT.SARADOMIN
        mock_find_emoji.return_value = ":saradomin:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock()
        mock_view_menu.return_value = mock_menu

        high_score_breakdown = ScoreBreakdown(
            [SkillScore("Attack", None, 1, "Attack", 200000000, 99, 50000)], [], [], []
        )

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = high_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        mock_menu.start.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_default_player_self(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock()
        mock_view_menu.return_value = mock_menu

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_breakdown(self.interaction, None)

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_boss_pagination(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":boss:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock()
        mock_view_menu.return_value = mock_menu

        many_bosses = []
        for i in range(30):
            many_bosses.append(ActivityScore(f"Boss{i}", None, i, f"Boss{i}", 100, 10))

        large_score_breakdown = ScoreBreakdown(
            self.sample_skills, self.sample_clues, self.sample_raids, many_bosses
        )

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = large_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        self.assertGreater(mock_menu.add_page.call_count, 4)
        mock_menu.start.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_empty_score_data(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock()
        mock_view_menu.return_value = mock_menu

        empty_score_breakdown = ScoreBreakdown([], [], [], [])

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = empty_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        mock_menu.start.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_bosses_with_zero_points_filtered(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":boss:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock()
        mock_view_menu.return_value = mock_menu

        bosses_with_zero_points = [
            ActivityScore("Boss1", None, 1, "Boss1", 100, 10),
            ActivityScore("Boss2", None, 2, "Boss2", 0, 0),
            ActivityScore("Boss3", None, 3, "Boss3", 50, 5),
        ]

        score_breakdown = ScoreBreakdown(
            self.sample_skills,
            self.sample_clues,
            self.sample_raids,
            bosses_with_zero_points,
        )

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        mock_menu.start.assert_called_once()
