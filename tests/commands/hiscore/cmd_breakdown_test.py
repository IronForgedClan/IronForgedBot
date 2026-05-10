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
        from ironforgedbot.commands.hiscore.cmd_breakdown import (
            cmd_breakdown,
            _build_embed_description,
            _build_boss_embeds,
            _build_activity_embed,
            _build_rank_ladder_embed,
            _resolve_rank_display,
            _BREAKDOWN_STATIC_DESCRIPTION,
        )


class TestBuildEmbedDescription(unittest.TestCase):
    def test_without_points_label_returns_total_points_format(self):
        result = _build_embed_description(":iron:", "TestUser", 1500)

        self.assertIn("**Member:** :iron: TestUser", result)
        self.assertIn("**Total Points:** 1,500", result)
        self.assertIn(_BREAKDOWN_STATIC_DESCRIPTION, result)

    def test_with_points_label_and_value_returns_category_format(self):
        result = _build_embed_description(
            ":iron:", "TestUser", 1500, "Skilling Points", 300
        )

        self.assertIn("**Member:** :iron: TestUser", result)
        self.assertIn("**Skilling Points:** 300/1,500", result)
        self.assertIn(_BREAKDOWN_STATIC_DESCRIPTION, result)

    def test_with_points_label_includes_percentage(self):
        result = _build_embed_description(
            ":iron:", "TestUser", 1000, "Bossing Points", 500
        )

        self.assertIn("50%", result)

    def test_with_only_points_label_falls_back_to_total_format(self):
        result = _build_embed_description(
            ":iron:", "TestUser", 1500, "Skilling Points", None
        )

        self.assertIn("**Total Points:**", result)
        self.assertNotIn("Skilling Points", result)

    def test_with_only_points_value_falls_back_to_total_format(self):
        result = _build_embed_description(":iron:", "TestUser", 1500, None, 300)

        self.assertIn("**Total Points:**", result)

    def test_large_numbers_formatted_with_commas(self):
        result = _build_embed_description(":god:", "TestUser", 25000)

        self.assertIn("25,000", result)


class TestResolveRankDisplay(unittest.TestCase):
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji",
        return_value=":saradomin:",
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.get_god_alignment_from_member",
        return_value=GOD_ALIGNMENT.SARADOMIN,
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points",
        return_value=discord.Color.blue(),
    )
    def test_god_rank_with_alignment(self, mock_color, mock_alignment, mock_emoji):
        member = create_test_member("TestUser", [ROLE.MEMBER])

        rank_icon, rank_color, god_alignment = _resolve_rank_display(
            member, 25000, RANK.GOD
        )

        self.assertEqual(rank_icon, ":saradomin:")
        self.assertEqual(rank_color, discord.Color.blue())
        self.assertEqual(god_alignment, GOD_ALIGNMENT.SARADOMIN)
        mock_alignment.assert_called_once_with(member)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":god:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.get_god_alignment_from_member",
        return_value=None,
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points",
        return_value=discord.Color.gold(),
    )
    def test_god_rank_without_alignment(self, mock_color, mock_alignment, mock_emoji):
        member = create_test_member("TestUser", [ROLE.MEMBER])

        rank_icon, rank_color, god_alignment = _resolve_rank_display(
            member, 25000, RANK.GOD
        )

        self.assertIsNone(god_alignment)
        self.assertEqual(rank_icon, ":god:")

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":iron:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points",
        return_value=discord.Color.greyple(),
    )
    def test_non_god_rank_returns_none_alignment(self, mock_color, mock_emoji):
        member = create_test_member("TestUser", [ROLE.MEMBER])

        rank_icon, rank_color, god_alignment = _resolve_rank_display(
            member, 0, RANK.IRON
        )

        self.assertIsNone(god_alignment)
        self.assertEqual(rank_icon, ":iron:")
        self.assertEqual(rank_color, discord.Color.greyple())

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":iron:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points",
        return_value=discord.Color.greyple(),
    )
    def test_none_member_non_god_rank(self, mock_color, mock_emoji):
        rank_icon, rank_color, god_alignment = _resolve_rank_display(None, 0, RANK.IRON)

        self.assertIsNone(god_alignment)
        self.assertEqual(rank_icon, ":iron:")


class TestBuildBossEmbeds(unittest.TestCase):
    def _make_boss(self, name: str, points: int, kc: int = 10) -> ActivityScore:
        return ActivityScore(name, None, 1, name, kc, points)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_zero_point_bosses_are_excluded(self, mock_embed, mock_emoji):
        bosses = [
            self._make_boss("Boss1", 100),
            self._make_boss("Boss2", 0),
            self._make_boss("Boss3", 50),
        ]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 1500
        )

        total_boss_fields = sum(
            1 for e in embeds for f in e.fields if f.name and "points" in f.name
        )
        self.assertEqual(total_boss_fields, 2)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_all_zero_point_bosses_returns_single_empty_embed(
        self, mock_embed, mock_emoji
    ):
        bosses = [self._make_boss("Boss1", 0), self._make_boss("Boss2", 0)]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 0
        )

        self.assertEqual(len(embeds), 1)
        self.assertEqual(len([f for f in embeds[0].fields if f.name]), 0)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_exactly_24_bosses_produces_single_page(self, mock_embed, mock_emoji):
        bosses = [self._make_boss(f"Boss{i}", 100) for i in range(24)]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 2400
        )

        self.assertEqual(len(embeds), 1)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_25_bosses_produces_two_pages(self, mock_embed, mock_emoji):
        bosses = [self._make_boss(f"Boss{i}", 100) for i in range(25)]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 2500
        )

        self.assertEqual(len(embeds), 2)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_last_page_padded_to_multiple_of_three(self, mock_embed, mock_emoji):
        # 25 bosses: 24 on page 1, 1 on page 2 — page 2 needs 2 padding fields
        bosses = [self._make_boss(f"Boss{i}", 100) for i in range(25)]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 2500
        )

        last_page = embeds[-1]
        self.assertEqual(len(last_page.fields) % 3, 0)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_multi_page_titles_include_page_numbers(self, mock_embed, mock_emoji):
        bosses = [self._make_boss(f"Boss{i}", 100) for i in range(25)]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 2500
        )

        self.assertIn("(1/2)", embeds[0].title)
        self.assertIn("(2/2)", embeds[1].title)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_single_page_title_has_no_page_numbers(self, mock_embed, mock_emoji):
        bosses = [self._make_boss("Boss1", 100)]

        embeds = _build_boss_embeds(
            bosses, ":iron:", discord.Color.greyple(), "TestUser", 100
        )

        self.assertNotIn("(1/1)", embeds[0].title)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":boss:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_no_bosses_returns_single_embed(self, mock_embed, mock_emoji):
        embeds = _build_boss_embeds(
            [], ":iron:", discord.Color.greyple(), "TestUser", 0
        )

        self.assertEqual(len(embeds), 1)


class TestBuildActivityEmbed(unittest.TestCase):
    def _make_item(self, name: str, points: int, kc: int = 5) -> ActivityScore:
        return ActivityScore(name, None, 1, name, kc, points)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":clue:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_field_added_for_each_item(self, mock_embed, mock_emoji):
        items = [self._make_item("Clue1", 50), self._make_item("Clue2", 100)]

        embed = _build_activity_embed(
            "Clues",
            items,
            "Clue Points",
            ":iron:",
            discord.Color.greyple(),
            "TestUser",
            1500,
            lambda item: f"{item.kc} completions",
        )

        self.assertEqual(len(embed.fields), 2)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":clue:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_value_formatter_is_applied(self, mock_embed, mock_emoji):
        items = [self._make_item("Clue1", 50, kc=7)]
        formatter = lambda item: f"custom:{item.kc}"

        embed = _build_activity_embed(
            "Clues",
            items,
            "Clue Points",
            ":iron:",
            discord.Color.greyple(),
            "TestUser",
            1500,
            formatter,
        )

        self.assertEqual(embed.fields[0].value, "custom:7")

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":clue:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_title_includes_provided_title_suffix(self, mock_embed, mock_emoji):
        items = [self._make_item("Clue1", 50)]

        embed = _build_activity_embed(
            "Raids",
            items,
            "Raid Points",
            ":iron:",
            discord.Color.greyple(),
            "TestUser",
            1500,
            lambda item: "val",
        )

        self.assertIn("Raids", embed.title)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":clue:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_empty_items_list_produces_no_fields(self, mock_embed, mock_emoji):
        embed = _build_activity_embed(
            "Clues",
            [],
            "Clue Points",
            ":iron:",
            discord.Color.greyple(),
            "TestUser",
            1500,
            lambda item: "val",
        )

        self.assertEqual(len(embed.fields), 0)


class TestBuildRankLadderEmbed(unittest.TestCase):
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":icon:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_non_god_rank_adds_progress_field(self, mock_embed, mock_emoji):
        embed = _build_rank_ladder_embed(
            "TestUser", RANK.IRON, ":iron:", discord.Color.greyple(), 0, None
        )

        field_names = [f.name for f in embed.fields]
        self.assertIn("Your Progress", field_names)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":icon:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_god_rank_with_alignment_adds_god_alignment_field(
        self, mock_embed, mock_emoji
    ):
        embed = _build_rank_ladder_embed(
            "TestUser",
            RANK.GOD,
            ":saradomin:",
            discord.Color.blue(),
            25000,
            GOD_ALIGNMENT.SARADOMIN,
        )

        field_names = [f.name for f in embed.fields]
        self.assertIn("God Alignment", field_names)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":icon:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_god_rank_without_alignment_shows_unaligned(self, mock_embed, mock_emoji):
        embed = _build_rank_ladder_embed(
            "TestUser", RANK.GOD, ":god:", discord.Color.gold(), 25000, None
        )

        alignment_field = next(f for f in embed.fields if f.name == "God Alignment")
        self.assertIn("Unaligned", alignment_field.value)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":icon:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_current_rank_row_includes_arrow_with_display_name(
        self, mock_embed, mock_emoji
    ):
        embed = _build_rank_ladder_embed(
            "TestUser", RANK.IRON, ":iron:", discord.Color.greyple(), 0, None
        )

        iron_field = next(
            (f for f in embed.fields if "Iron" in f.name and "←" in f.name), None
        )
        self.assertIsNotNone(iron_field)
        self.assertIn("TestUser", iron_field.name)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji", return_value=":icon:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed",
        side_effect=lambda title, desc, color: discord.Embed(
            title=title, description=desc
        ),
    )
    def test_other_ranks_do_not_have_arrow(self, mock_embed, mock_emoji):
        embed = _build_rank_ladder_embed(
            "TestUser", RANK.IRON, ":iron:", discord.Color.greyple(), 0, None
        )

        non_iron_fields = [
            f
            for f in embed.fields
            if "Iron" not in f.name and f.name != "Your Progress"
        ]
        for field in non_iron_fields:
            self.assertNotIn("←", field.name)


class TestCmdBreakdown(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.prospect_user = create_test_member("ProspectUser", [PROSPECT_ROLE_NAME])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

        self.sample_score_breakdown = create_test_score_data(
            skills_count=2, activities_count=4
        )

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
    async def test_cmd_breakdown_hiscores_error_and_http_exception(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service

        for exc in [HiscoresError("API Error"), HttpException("Network Error")]:
            with self.subTest(exception=type(exc).__name__):
                mock_send_error.reset_mock()
                mock_score_service.get_player_score.side_effect = exc

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
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.has_prospect_role")
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
        self.assertEqual(mock_menu.add_button.call_count, 3)
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
    async def test_cmd_breakdown_default_player_uses_display_name(
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
            self.interaction.guild,
            self.interaction.user.display_name,
            must_be_member=False,
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

        many_bosses = [
            ActivityScore(f"Boss{i}", None, i, f"Boss{i}", 100, 10) for i in range(30)
        ]

        large_score_breakdown = ScoreBreakdown(
            self.sample_skills, self.sample_clues, self.sample_raids, many_bosses
        )

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = large_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        # 1 skill + 2 boss pages (30 bosses, 24 per page) + 1 raid + 1 clue + 1 rank ladder = 6
        self.assertEqual(mock_menu.add_page.call_count, 6)
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

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = ScoreBreakdown(
            [], [], [], []
        )

        await cmd_breakdown(self.interaction, "TestUser")

        mock_menu.start.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_menu_start_raises_sends_error_response(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_send_error,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock(side_effect=Exception("Menu failed"))
        mock_menu.stop = AsyncMock()
        mock_view_menu.return_value = mock_menu

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        mock_menu.stop.assert_called_once()
        mock_send_error.assert_called_once_with(
            self.interaction,
            "An unexpected error occurred while generating the breakdown. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.get_rank_color_from_points")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu")
    async def test_cmd_breakdown_menu_start_raises_stop_also_raises(
        self,
        mock_view_menu,
        mock_build_embed,
        mock_find_emoji,
        mock_get_color,
        mock_get_rank,
        mock_validate,
        mock_http,
        mock_get_score_service,
        mock_send_error,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = ":iron:"

        mock_embed = Mock()
        mock_embed.fields = []
        mock_build_embed.return_value = mock_embed

        mock_menu = Mock()
        mock_menu.start = AsyncMock(side_effect=Exception("Menu failed"))
        mock_menu.stop = AsyncMock(side_effect=Exception("Stop also failed"))
        mock_view_menu.return_value = mock_menu

        mock_score_service = AsyncMock()
        mock_get_score_service.return_value = mock_score_service
        mock_score_service.get_player_score.return_value = self.sample_score_breakdown

        await cmd_breakdown(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An unexpected error occurred while generating the breakdown. Please try again.",
        )
