import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

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
        from ironforgedbot.commands.hiscore.cmd_score import cmd_score


class TestCmdScore(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.prospect_user = create_test_member("ProspectUser", [PROSPECT_ROLE_NAME])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

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

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresError("API Error")

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

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HttpException("Network Error")

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

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresNotFound(
            "No hiscores found"
        )

        await cmd_score(self.interaction, "TestUser")

        mock_send_no_hiscore.assert_called_once_with(self.interaction, "TestUser")

    @patch("ironforgedbot.commands.hiscore.cmd_score.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_score.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_score.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_score.send_not_clan_member")
    async def test_cmd_score_non_member_hiscores_not_found(
        self, mock_send_not_clan, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (None, "NonMember")  # Not a guild member

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.side_effect = HiscoresNotFound(
            "No hiscores found"
        )

        await cmd_score(self.interaction, "NonMember")

        # Should create empty score breakdown and eventually call send_not_clan_member
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
        mock_check_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.prospect_user, "ProspectUser")
        mock_check_role.return_value = True  # Is prospect
        mock_find_emoji.return_value = ":prospect:"

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

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
        mock_check_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        non_member = create_test_member("NonMember", [])  # No roles
        mock_validate.return_value = (non_member, "NonMember")
        mock_check_role.return_value = False  # Not a member
        mock_find_emoji.return_value = ":iron:"

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_score(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

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
        mock_check_role,
        mock_find_emoji,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"
        # First call checks for PROSPECT role (should return False), second call checks for MEMBER role (should return True)
        mock_check_role.side_effect = [False, True]
        mock_render_percentage.return_value = "45%"

        # Mock the embed that gets built - create a real embed that can have fields added
        mock_embed = Mock()
        mock_embed.title = ":iron: TestUser | Score: 1,675"
        mock_embed.fields = []

        # Mock add_field to track field additions
        def add_field_side_effect(name=None, value=None, inline=True):
            field = Mock()
            field.name = name
            field.value = value
            field.inline = inline
            mock_embed.fields.append(field)
            return None

        mock_embed.add_field = lambda *args, **kwargs: add_field_side_effect(
            *args, **kwargs
        )
        mock_build_embed.return_value = mock_embed

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_score(self.interaction, "TestUser")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
        mock_score_service.get_player_score.assert_called_once_with("TestUser")
        self.interaction.followup.send.assert_called_once()

        # Verify build_response_embed was called with correct parameters
        mock_build_embed.assert_called_once_with(
            ":iron: TestUser | Score: 1,675", "", discord.Color.greyple()
        )

        # Verify add_field was called correctly
        self.assertEqual(len(mock_embed.fields), 3)

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
        mock_check_role,
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
        # First call checks for PROSPECT role (should return False), second call checks for MEMBER role (should return True)
        mock_check_role.side_effect = [False, True]

        # Mock build_response_embed
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_score(self.interaction, None)  # No player specified

        # Should use interaction.user.display_name which is "TestUser"
        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )

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
        mock_check_role,
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
        # First call checks for PROSPECT role (should return False), second call checks for MEMBER role (should return True)
        mock_check_role.side_effect = [False, True]

        # Mock the embed that gets built - create a real embed that can have fields added
        mock_embed = Mock()
        mock_embed.title = ":saradomin: TestUser | Score: 50,000"
        mock_embed.fields = []

        # Mock add_field to track field additions
        def add_field_side_effect(name=None, value=None, inline=True):
            field = Mock()
            field.name = name
            field.value = value
            field.inline = inline
            mock_embed.fields.append(field)
            return None

        mock_embed.add_field = lambda *args, **kwargs: add_field_side_effect(
            *args, **kwargs
        )
        mock_build_embed.return_value = mock_embed

        # High points to trigger GOD rank
        high_score_breakdown = ScoreBreakdown(
            [SkillScore("Attack", None, 1, "Attack", 200000000, 99, 50000)], [], [], []
        )

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = high_score_breakdown

        await cmd_score(self.interaction, "TestUser")

        # Verify build_response_embed was called
        mock_build_embed.assert_called_once()

        # Should have 3 fields: Skill Points, Activity Points, and God alignment
        self.assertEqual(len(mock_embed.fields), 3)

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
        mock_check_role,
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
        # First call checks for PROSPECT role (should return False), second call checks for MEMBER role (should return True)
        mock_check_role.side_effect = [False, True]

        # Mock build_response_embed
        mock_embed = Mock()
        mock_embed.title = ":iron: TestUser | Score: 0"
        mock_build_embed.return_value = mock_embed

        empty_score_breakdown = ScoreBreakdown([], [], [], [])

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = empty_score_breakdown

        await cmd_score(self.interaction, "TestUser")

        # Verify build_response_embed was called with correct title
        mock_build_embed.assert_called_once_with(
            ":iron: TestUser | Score: 0", "", discord.Color.greyple()
        )

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
        mock_check_role,
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
        # First call checks for PROSPECT role (should return False), second call checks for MEMBER role (should return True)
        mock_check_role.side_effect = [False, True]
        mock_render_percentage.return_value = "89%"

        # Mock the embed that gets built
        mock_embed = Mock()
        mock_embed.fields = []

        # Mock add_field to track field additions
        def add_field_side_effect(name=None, value=None, inline=True):
            field = Mock()
            field.name = name
            field.value = value
            field.inline = inline
            mock_embed.fields.append(field)
            return None

        mock_embed.add_field = lambda *args, **kwargs: add_field_side_effect(
            *args, **kwargs
        )
        mock_build_embed.return_value = mock_embed

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_score(self.interaction, "TestUser")

        # Verify the correct fields were added
        self.assertEqual(len(mock_embed.fields), 3)

        # Check that skill points and activity points fields were added correctly
        self.assertEqual(len(mock_embed.fields), 3)

        # Check the field values that were added
        skill_field = mock_embed.fields[0]
        activity_field = mock_embed.fields[1]

        self.assertEqual(skill_field.name, "Skill Points")
        self.assertIn("1,500", skill_field.value)
        self.assertEqual(activity_field.name, "Activity Points")
        self.assertIn("175", activity_field.value)
