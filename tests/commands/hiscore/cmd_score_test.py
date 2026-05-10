import unittest
from unittest.mock import ANY, AsyncMock, Mock, patch

import discord

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE, PROSPECT_ROLE_NAME
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
        from ironforgedbot.commands.hiscore.cmd_score import (
            cmd_score,
            _build_rank_progress_bar,
            _get_score_history,
        )
        from ironforgedbot.commands.hiscore.score_utils import _calculate_points


def _make_embed_mock() -> Mock:
    mock_embed = Mock()
    mock_embed.fields = []

    def add_field_side_effect(name=None, value=None, inline=True):
        field = Mock()
        field.name = name
        field.value = value
        field.inline = inline
        mock_embed.fields.append(field)

    mock_embed.add_field = lambda *args, **kwargs: add_field_side_effect(
        *args, **kwargs
    )
    return mock_embed


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestBuildRankProgressBar(unittest.TestCase):
    def test_zero_progress(self):
        result = _build_rank_progress_bar(0, 0, 1000, ":iron:", ":mithril:")
        self.assertIn(":iron:", result)
        self.assertIn(":mithril:", result)
        self.assertNotIn("▰", result)

    def test_full_progress(self):
        result = _build_rank_progress_bar(1000, 0, 1000, ":iron:", ":mithril:")
        self.assertNotIn("▱", result)

    def test_half_progress(self):
        result = _build_rank_progress_bar(500, 0, 1000, ":iron:", ":mithril:")
        filled = result.count("▰")
        empty = result.count("▱")
        self.assertEqual(filled, 10)
        self.assertEqual(empty, 10)

    def test_zero_span_returns_full_bar(self):
        result = _build_rank_progress_bar(5000, 5000, 5000, ":god:", ":god:")
        self.assertNotIn("▱", result)

    def test_clamps_below_zero(self):
        result = _build_rank_progress_bar(-100, 0, 1000, ":iron:", ":mithril:")
        self.assertNotIn("▰", result)

    def test_clamps_above_max(self):
        result = _build_rank_progress_bar(9999, 0, 1000, ":iron:", ":mithril:")
        self.assertNotIn("▱", result)

    def test_includes_percentage(self):
        with patch(
            "ironforgedbot.commands.hiscore.cmd_score.render_percentage",
            return_value="50%",
        ):
            result = _build_rank_progress_bar(500, 0, 1000, ":iron:", ":mithril:")
        self.assertIn("50%", result)


class TestCalculatePoints(unittest.TestCase):
    def test_sums_all_categories(self):
        skills = [SkillScore("Attack", None, 1, "Attack", 13034000, 99, 1000)]
        bosses = [ActivityScore("Zulrah", None, 1, "Zulrah", 200, 100)]
        clues = [ActivityScore("Beginner", None, 1, "Beginner", 100, 50)]
        raids = [ActivityScore("CoX", None, 1, "CoX", 50, 25)]
        data = ScoreBreakdown(skills, clues, raids, bosses)

        skill_pts, activity_pts, total = _calculate_points(data)

        self.assertEqual(skill_pts, 1000)
        self.assertEqual(activity_pts, 175)
        self.assertEqual(total, 1175)

    def test_empty_breakdown_returns_zeros(self):
        data = ScoreBreakdown([], [], [], [])
        skill_pts, activity_pts, total = _calculate_points(data)
        self.assertEqual(skill_pts, 0)
        self.assertEqual(activity_pts, 0)
        self.assertEqual(total, 0)


class TestGetScoreHistory(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.hiscore.cmd_score.db")
    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreHistoryService")
    async def test_returns_deltas_for_available_periods(
        self, mock_service_cls, mock_db
    ):
        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_service = AsyncMock()
        mock_service_cls.return_value = mock_service
        mock_service.get_score_history.return_value = {7: 900, 14: 800}

        result = await _get_score_history(123456, 1000)

        self.assertEqual(result[7], 100)
        self.assertEqual(result[14], 200)
        self.assertNotIn(30, result)

    @patch("ironforgedbot.commands.hiscore.cmd_score.db")
    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreHistoryService")
    async def test_returns_empty_dict_on_exception(self, mock_service_cls, mock_db):
        mock_db.get_session.side_effect = Exception("DB error")

        result = await _get_score_history(123456, 1000)

        self.assertEqual(result, {})

    @patch("ironforgedbot.commands.hiscore.cmd_score.db")
    @patch("ironforgedbot.commands.hiscore.cmd_score.ScoreHistoryService")
    async def test_returns_empty_dict_when_no_snapshots(
        self, mock_service_cls, mock_db
    ):
        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_service = AsyncMock()
        mock_service_cls.return_value = mock_service
        mock_service.get_score_history.return_value = {}

        result = await _get_score_history(123456, 1000)

        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Integration tests for cmd_score command handler
# ---------------------------------------------------------------------------


class TestCmdScore(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.prospect_user = create_test_member("ProspectUser", [PROSPECT_ROLE_NAME])
        self.interaction = create_mock_discord_interaction(user=self.test_user)
        self.mock_embed = _make_embed_mock()

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
            self.sample_skills, self.sample_clues, self.sample_raids, self.sample_bosses
        )

    def _make_score_service_mock(self, return_value=None, side_effect=None):
        mock_score_service = AsyncMock()
        if side_effect:
            mock_score_service.get_player_score.side_effect = side_effect
        else:
            mock_score_service.get_player_score.return_value = (
                return_value
                if return_value is not None
                else self.sample_score_breakdown
            )
        return mock_score_service

    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    async def test_cmd_score_validation_error(self, mock_validate, mock_send_error):
        mock_validate.side_effect = Exception("Invalid player name")

        await cmd_score(self.interaction, "BadName")

        mock_send_error.assert_called_once_with(
            self.interaction, "Invalid player name", report_to_channel=False
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    async def test_cmd_score_hiscores_error(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresError("API Error")
        )

        await cmd_score(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_error_response")
    async def test_cmd_score_http_exception(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HttpException("Network Error")
        )

        await cmd_score(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_member_no_hiscore_values")
    async def test_cmd_score_member_no_hiscores(
        self, mock_send_no_hiscore, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresNotFound("No hiscores found")
        )

        await cmd_score(self.interaction, "TestUser")

        mock_send_no_hiscore.assert_called_once_with(
            self.interaction, self.test_user.display_name
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_not_clan_member")
    async def test_cmd_score_non_member_hiscores_not_found(
        self, mock_send_not_clan, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (None, "NonMember")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresNotFound("No hiscores found")
        )

        await cmd_score(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_prospect_response")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    async def test_cmd_score_prospect_response(
        self,
        mock_find_emoji,
        mock_send_prospect,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.prospect_user, "ProspectUser")
        mock_has_prospect_role.return_value = True
        mock_find_emoji.return_value = ":prospect:"
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "ProspectUser")

        mock_send_prospect.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_not_clan_member")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    async def test_cmd_score_not_clan_member_response(
        self,
        mock_find_emoji,
        mock_send_not_clan,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        non_member = create_test_member("NonMember", [])
        mock_validate.return_value = (non_member, "NonMember")
        mock_has_prospect_role.return_value = False
        mock_find_emoji.return_value = ":iron:"
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_cmd_score_success_member(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        # has_prospect_role called once (returns False), check_member_has_role called once (returns True)
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "45%"
        mock_get_history.return_value = {}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
        mock_get_score_service.return_value.get_player_score.assert_called_once_with(
            "TestUser"
        )
        self.interaction.followup.send.assert_called_once()

        mock_build_embed.assert_called_once_with(
            "🏆 Member Score", ANY, discord.Color.greyple()
        )

        # Member, Rank, Next Rank | Total Points, Skill Points, Activity Points | Rank Progress = 7 fields
        self.assertEqual(len(mock_embed.fields), 7)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_cmd_score_default_player_self(
        self,
        mock_build_embed,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_get_history.return_value = {}
        mock_build_embed.return_value = Mock()
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, None)

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_god_alignment_from_member")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_cmd_score_god_rank_saradomin(
        self,
        mock_build_embed,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.GOD
        mock_get_color.return_value = discord.Color.blue()
        mock_get_god_alignment.return_value = GOD_ALIGNMENT.SARADOMIN
        mock_find_emoji.return_value = ":saradomin:"
        mock_has_prospect_role.return_value = False
        mock_get_history.return_value = {}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed

        high_score_breakdown = ScoreBreakdown(
            [SkillScore("Attack", None, 1, "Attack", 200000000, 99, 50000)], [], [], []
        )
        mock_get_score_service.return_value = self._make_score_service_mock(
            return_value=high_score_breakdown
        )

        await cmd_score(self.interaction, "TestUser")

        mock_build_embed.assert_called_once()

        # Member, Current Rank, God Alignment | Total Points, Skill Points, Activity Points = 6 fields
        self.assertEqual(len(mock_embed.fields), 6)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_cmd_score_empty_score_data(
        self,
        mock_build_embed,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_get_history.return_value = {}
        mock_build_embed.return_value = Mock()
        mock_get_score_service.return_value = self._make_score_service_mock(
            return_value=ScoreBreakdown([], [], [], [])
        )

        await cmd_score(self.interaction, "TestUser")

        mock_build_embed.assert_called_once_with(
            "🏆 Member Score", ANY, discord.Color.greyple()
        )

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_cmd_score_points_calculation(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "89%"
        mock_get_history.return_value = {}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        # Member, Rank, Next Rank | Total Points, Skill Points, Activity Points | Rank Progress = 7 fields
        self.assertEqual(len(mock_embed.fields), 7)

        score_field = mock_embed.fields[3]
        skill_field = mock_embed.fields[4]
        activity_field = mock_embed.fields[5]

        self.assertEqual(score_field.name, "Total Points")
        self.assertIn("1,675", score_field.value)
        self.assertEqual(skill_field.name, "Skill Points")
        self.assertIn("1,500", skill_field.value)
        self.assertEqual(activity_field.name, "Activity Points")
        self.assertIn("175", activity_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_score_history_all_periods_present(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "45%"
        mock_get_history.return_value = {7: 1250, 14: 2100, 30: 3400}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        # Member, Rank, Next Rank | Total Points, Skill Points, Activity Points
        # | Score History (7d), (14d), (30d) | Rank Progress = 10 fields
        self.assertEqual(len(mock_embed.fields), 10)

        self.assertEqual(mock_embed.fields[6].name, "Score History")
        self.assertIn("7d", mock_embed.fields[6].value)
        self.assertTrue(mock_embed.fields[6].inline)

        self.assertEqual(mock_embed.fields[7].name, EMPTY_SPACE)
        self.assertIn("14d", mock_embed.fields[7].value)
        self.assertTrue(mock_embed.fields[7].inline)

        self.assertEqual(mock_embed.fields[8].name, EMPTY_SPACE)
        self.assertIn("30d", mock_embed.fields[8].value)
        self.assertTrue(mock_embed.fields[8].inline)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_score_history_omitted_when_no_history(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "45%"
        mock_get_history.return_value = {}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        # Member, Rank, Next Rank | Total Points, Skill Points, Activity Points | Rank Progress = 7 fields
        self.assertEqual(len(mock_embed.fields), 7)
        field_names = [f.name for f in mock_embed.fields]
        self.assertNotIn("Score History", field_names)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_score_history_partial_periods(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "45%"
        mock_get_history.return_value = {7: 500}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        # Member, Rank, Next Rank | Total Points, Skill Points, Activity Points
        # | Score History (7d only) | Rank Progress = 8 fields
        self.assertEqual(len(mock_embed.fields), 8)

        self.assertEqual(mock_embed.fields[6].name, "Score History")
        self.assertIn("7d", mock_embed.fields[6].value)
        self.assertTrue(mock_embed.fields[6].inline)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_rank_progress_field_shows_progress_bar(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "45%"
        mock_get_history.return_value = {}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        rank_progress_field = mock_embed.fields[6]
        self.assertEqual(rank_progress_field.name, "Rank Progress")
        self.assertFalse(rank_progress_field.inline)
        self.assertIn("▰", rank_progress_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_score._get_score_history")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.get_next_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_score.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_score.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_score.render_percentage")
    @patch("ironforgedbot.commands.hiscore.cmd_score.build_response_embed")
    async def test_next_rank_field_shows_points_needed(
        self,
        mock_build_embed,
        mock_render_percentage,
        mock_has_prospect_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_get_history,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        mock_has_prospect_role.return_value = False
        mock_render_percentage.return_value = "45%"
        mock_get_history.return_value = {}

        mock_embed = _make_embed_mock()
        mock_build_embed.return_value = mock_embed
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_score(self.interaction, "TestUser")

        next_rank_field = mock_embed.fields[2]
        self.assertEqual(next_rank_field.name, "Next Rank")
        self.assertIn("Mithril", next_rank_field.value)
        self.assertIn("pts", next_rank_field.value)
        self.assertTrue(next_rank_field.inline)
