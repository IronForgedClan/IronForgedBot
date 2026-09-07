import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedcore.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedcore.common.roles import ROLE
from ironforgedcore.common.role_names import PROSPECT_ROLE_NAME
from ironforgedcore.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedcore.http import HttpException
from ironforgedcore.models.score import (
    ActivityScore,
    NextPointProgress,
    ScoreBreakdown,
    SkillScore,
)
from ironforgedcore.storage import data as data_module
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)


def _populate_data_module() -> None:
    data_module.set_data(
        skills=[
            {
                "name": "Attack",
                "display_order": 1,
                "emoji_key": "Attack",
                "xp_per_point": 100000,
                "xp_per_point_post_99": 300000,
                "xp_per_hour": [{"end_xp": 200000000, "rate": 100000}],
            },
            {
                "name": "Defence",
                "display_order": 7,
                "emoji_key": "Defence",
                "xp_per_point": 100000,
                "xp_per_point_post_99": 300000,
                "xp_per_hour": [{"end_xp": 200000000, "rate": 100000}],
            },
        ],
        clues=[
            {
                "name": "Clue Scrolls (beginner)",
                "display_name": "Beginner",
                "display_order": 1,
                "emoji_key": "Beginner_Clue",
                "kc_per_point": 10,
                "kc_per_hour": 20,
            },
        ],
        raids=[
            {
                "name": "Chambers of Xeric",
                "display_order": 1,
                "emoji_key": "Chambers_of_Xeric",
                "kc_per_point": 0.8,
                "kc_per_hour": 2,
            },
        ],
        bosses=[
            {
                "name": "Zulrah",
                "display_order": 59,
                "emoji_key": "Zulrah",
                "kc_per_point": 12,
                "kc_per_hour": 5,
            },
        ],
    )


with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    with patch(
        "ironforgedbot.common.logging_utils.log_command_execution",
        lambda *a, **kw: lambda f: f,
    ):
        from ironforgedbot.commands.hiscore.cmd_point_progress import cmd_point_progress

from ironforgedbot.commands.hiscore.cmd_point_progress import (  # noqa: E402
    _TOP_N,
    _build_list_embed,
    _build_summary_embed,
)


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


def _make_breakdown() -> ScoreBreakdown:
    return ScoreBreakdown(
        skills=[
            SkillScore("Attack", None, 1, "Attack", 80000, 70, 0),
            SkillScore("Defence", None, 7, "Defence", 200000, 99, 2),
        ],
        clues=[
            ActivityScore(
                "Clue Scrolls (beginner)", "Beginner", 1, "Beginner_Clue", 5, 0
            )
        ],
        raids=[
            ActivityScore("Chambers of Xeric", None, 1, "Chambers_of_Xeric", 10, 12)
        ],
        bosses=[ActivityScore("Zulrah", None, 59, "Zulrah", 11, 0)],
    )


def _make_proximity_result() -> list[NextPointProgress]:
    return [
        NextPointProgress(
            category="skill",
            name="Defence",
            display_name=None,
            emoji_key="Defence",
            current=200000,
            points=2,
            progress_percent=0.0,
            remaining_to_next=100000,
            unit="xp",
            time_hours=1.0,
        ),
        NextPointProgress(
            category="boss",
            name="Zulrah",
            display_name=None,
            emoji_key="Zulrah",
            current=1,
            points=0,
            progress_percent=0.083,
            remaining_to_next=11,
            unit="kc",
            time_hours=2.2,
        ),
        NextPointProgress(
            category="clue",
            name="Clue Scrolls (beginner)",
            display_name="Beginner",
            emoji_key="Beginner_Clue",
            current=5,
            points=0,
            progress_percent=0.5,
            remaining_to_next=5,
            unit="kc",
            time_hours=0.25,
        ),
    ]


class TestBuildSummaryEmbed(unittest.TestCase):
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"MITHRIL": 100},
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    def test_non_god_rank_includes_member_total_and_next(
        self, mock_build_embed, mock_find_emoji, mock_next_rank
    ):
        embed = _make_embed_mock()
        mock_build_embed.return_value = embed
        mock_find_emoji.return_value = ":iron:"
        mock_next_rank.return_value = RANK.MITHRIL

        result = _build_summary_embed(
            display_name="TestUser",
            rank_name=RANK.IRON,
            rank_icon=":iron:",
            rank_color=discord.Color.greyple(),
            god_alignment=None,
            points_total=42,
        )

        field_names = {f.name for f in result.fields if f.name}
        self.assertIn("Member", field_names)
        self.assertIn("Total Points", field_names)
        self.assertIn("Next Rank", field_names)
        self.assertNotIn("God Alignment", field_names)

        total_field = next(f for f in result.fields if f.name == "Total Points")
        self.assertEqual(total_field.value, "42")

        next_field = next(f for f in result.fields if f.name == "Next Rank")
        self.assertIn("Mithril", next_field.value)
        self.assertIn("58 pts", next_field.value)

    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"MITHRIL": 100},
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    def test_member_field_uses_rank_icon_for_non_god(
        self, mock_build_embed, mock_find_emoji, mock_next_rank
    ):
        embed = _make_embed_mock()
        mock_build_embed.return_value = embed
        mock_find_emoji.return_value = ":iron:"
        mock_next_rank.return_value = RANK.MITHRIL

        result = _build_summary_embed(
            display_name="TestUser",
            rank_name=RANK.IRON,
            rank_icon=":iron:",
            rank_color=discord.Color.greyple(),
            god_alignment=None,
            points_total=0,
        )

        member_field = next(f for f in result.fields if f.name == "Member")
        self.assertIn(":iron:", member_field.value)
        self.assertNotIn(":grass:", member_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    def test_god_rank_aligned_uses_alignment_icon_and_value(
        self, mock_build_embed, mock_find_emoji
    ):
        embed = _make_embed_mock()
        mock_build_embed.return_value = embed
        mock_find_emoji.side_effect = lambda key: f"<:{key.lower()}:123>"

        result = _build_summary_embed(
            display_name="TestUser",
            rank_name=RANK.GOD,
            rank_icon="<:saradominist:123>",
            rank_color=discord.Color.blue(),
            god_alignment=GOD_ALIGNMENT.SARADOMIN,
            points_total=25000,
        )

        member_field = next(f for f in result.fields if f.name == "Member")
        self.assertIn(":grass:", member_field.value)

        align_field = next(f for f in result.fields if f.name == "God Alignment")
        self.assertIn("Saradominist", align_field.value)
        self.assertIn(":saradominist:", align_field.value)

        self.assertNotIn("Next Rank", {f.name for f in result.fields})

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    def test_god_rank_unaligned_uses_italic_no_emoji(
        self, mock_build_embed, mock_find_emoji
    ):
        embed = _make_embed_mock()
        mock_build_embed.return_value = embed
        mock_find_emoji.side_effect = lambda key: f":{key.lower()}:"

        result = _build_summary_embed(
            display_name="TestUser",
            rank_name=RANK.GOD,
            rank_icon=":god:",
            rank_color=discord.Color.gold(),
            god_alignment=None,
            points_total=25000,
        )

        align_field = next(f for f in result.fields if f.name == "God Alignment")
        self.assertEqual(align_field.value, "_Unaligned_")
        self.assertNotIn(":god:", align_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    def test_summary_embed_drops_rsn_and_current_rank(
        self, mock_build_embed, mock_find_emoji
    ):
        mock_find_emoji.return_value = ":iron:"
        mock_build_embed.return_value = _make_embed_mock()

        non_god = _build_summary_embed(
            display_name="TestUser",
            rank_name=RANK.IRON,
            rank_icon=":iron:",
            rank_color=discord.Color.greyple(),
            god_alignment=None,
            points_total=0,
        )
        non_god_names = {f.name for f in non_god.fields if f.name}
        self.assertNotIn("RSN", non_god_names)
        self.assertNotIn("Current Rank", non_god_names)

        god = _build_summary_embed(
            display_name="TestUser",
            rank_name=RANK.GOD,
            rank_icon="<:saradominist:123>",
            rank_color=discord.Color.gold(),
            god_alignment=GOD_ALIGNMENT.SARADOMIN,
            points_total=25000,
        )
        god_names = {f.name for f in god.fields if f.name}
        self.assertNotIn("RSN", god_names)
        self.assertNotIn("Current Rank", god_names)


class TestBuildListEmbed(unittest.TestCase):
    def _make_progress(self, **kwargs) -> NextPointProgress:
        defaults = dict(
            category="skill",
            name="Defence",
            display_name=None,
            emoji_key="Defence",
            current=200000,
            points=2,
            progress_percent=0.0,
            remaining_to_next=100000,
            unit="xp",
            time_hours=1.0,
        )
        defaults.update(kwargs)
        return NextPointProgress(**defaults)

    def _build(self, proximity: list[NextPointProgress]) -> str:
        embed = _build_list_embed(proximity, discord.Color.greyple())
        return embed.description or ""

    def _table(self, proximity: list[NextPointProgress]) -> str:
        description = self._build(proximity)
        parts = description.split("```")
        return parts[1] if len(parts) >= 2 else description

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    def test_empty_proximity_shows_no_progress_field(self, mock_build_embed):
        embed = _make_embed_mock()
        mock_build_embed.return_value = embed

        result = _build_list_embed([], discord.Color.greyple())

        real = [f for f in result.fields if f.name]
        self.assertEqual(len(real), 1)
        self.assertEqual(real[0].name, "No progress yet")
        self.assertFalse(real[0].inline)

    def test_non_empty_list_render_as_table(self):
        description = self._build(
            [
                self._make_progress(name="A"),
                self._make_progress(name="B"),
            ]
        )

        self.assertIn("Point", description)
        self.assertIn("Next In", description)
        self.assertIn("Estimate", description)

    def test_table_renders_one_row_per_progress_entry(self):
        description = self._build(
            [
                self._make_progress(name="A"),
                self._make_progress(name="B"),
                self._make_progress(name="C"),
            ]
        )

        parts = description.split("```")
        inner = parts[1] if len(parts) >= 2 else ""
        data_rows = [
            line
            for line in inner.split("\n")
            if any(label in line for label in ("A", "B", "C"))
        ]
        self.assertEqual(len(data_rows), 3)

    def test_description_includes_wom_footer(self):
        description = self._build([self._make_progress()])

        self.assertIn("Wise Old Man", description)
        self.assertIn("https://wiseoldman.net/ehb/ironman", description)

    def test_row_label_prefers_display_name_for_clues(self):
        progress = self._make_progress(
            category="clue",
            name="Clue Scrolls (beginner)",
            display_name="Beginner",
            emoji_key="Beginner_Clue",
            remaining_to_next=5,
            unit="kc",
        )

        description = self._build([progress])

        self.assertIn("Beginner", description)
        self.assertNotIn("Clue Scrolls (beginner)", description)

    def test_row_label_falls_back_to_name_when_no_display_name(self):
        description = self._build([self._make_progress()])

        self.assertIn("Defence", description)

    def test_row_remaining_no_scientific_notation_for_large_xp(self):
        progress = self._make_progress(
            category="skill",
            name="Attack",
            emoji_key="Attack",
            current=17_483_000,
            points=130,
            remaining_to_next=3_940,
        )

        description = self._build([progress])

        self.assertIn("3,940 xp", description)
        self.assertNotIn("e+", description)
        self.assertNotIn("e-", description)

    def test_row_ehp_for_skill(self):
        progress = self._make_progress(
            category="skill",
            name="Attack",
            emoji_key="Attack",
            time_hours=2.5,
            remaining_to_next=100000,
            unit="xp",
        )

        description = self._build([progress])

        self.assertIn("100,000 xp", description)
        self.assertIn("2 hr 30 min", description)
        self.assertNotIn("ehp", self._table([progress]))

    def test_row_ehb_for_boss(self):
        progress = self._make_progress(
            category="boss",
            name="Zulrah",
            emoji_key="Zulrah",
            time_hours=1.0,
            remaining_to_next=11,
            unit="kc",
        )

        description = self._build([progress])

        self.assertIn("11 kc", description)
        self.assertIn("1 hr", description)
        self.assertNotIn("ehb", self._table([progress]))

    def test_row_ehb_for_raid(self):
        progress = self._make_progress(
            category="raid",
            name="Chambers of Xeric",
            display_name="Chambers of Xeric",
            emoji_key="Chambers_of_Xeric",
            time_hours=24.0,
            remaining_to_next=10,
            unit="kc",
        )

        description = self._build([progress])

        self.assertIn("10 kc", description)
        self.assertIn("1 d", description)
        self.assertNotIn("ehb", self._table([progress]))

    def test_row_ehb_for_clue(self):
        progress = self._make_progress(
            category="clue",
            name="Clue Scrolls (beginner)",
            display_name="Beginner",
            emoji_key="Beginner_Clue",
            time_hours=0.5,
            remaining_to_next=5,
            unit="kc",
        )

        description = self._build([progress])

        self.assertIn("5 kc", description)
        self.assertIn("30 min", description)
        self.assertNotIn("ehb", self._table([progress]))

    def test_row_ehp_renders_dash_when_time_hours_is_none(self):
        progress = self._make_progress(
            category="skill",
            name="Attack",
            emoji_key="Attack",
            time_hours=None,
            remaining_to_next=100000,
            unit="xp",
        )

        description = self._build([progress])

        self.assertIn("-```", description)
        self.assertIn("100,000 xp", description)


class TestListEmbedUsesTextAsciiTable(unittest.TestCase):
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.text_ascii_table")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.format_duration_hours")
    def test_calls_helper_with_expected_kwargs(
        self, mock_format, mock_build_embed, mock_table
    ):
        from ironforgedcore.models.score import NextPointProgress

        mock_build_embed.return_value = _make_embed_mock()
        mock_table.return_value = "rendered-table"
        mock_format.return_value = "1 hr ehb"

        _build_list_embed(
            [
                NextPointProgress(
                    category="skill",
                    name="Attack",
                    display_name=None,
                    emoji_key="Attack",
                    current=100000,
                    points=1,
                    progress_percent=0.0,
                    remaining_to_next=100000,
                    unit="xp",
                    time_hours=1.0,
                )
            ],
            discord.Color.greyple(),
        )

        mock_table.assert_called_once()
        call_kwargs = mock_table.call_args.kwargs
        self.assertEqual(call_kwargs["headers"], ["Point", "Next In", "Estimate"])
        self.assertEqual(call_kwargs["wrap_widths"], [20, None, None])
        self.assertEqual(call_kwargs["colalign"], ("left", "right", "right"))


@patch.dict("os.environ", VALID_CONFIG)
class TestCmdPointProgress(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _populate_data_module()

        self.test_user = create_test_member("TestUser", [ROLE.MEMBER], "TestUser")
        self.prospect_user = create_test_member(
            "ProspectUser", [PROSPECT_ROLE_NAME], "ProspectUser"
        )
        self.interaction = create_mock_discord_interaction(user=self.test_user)
        self.summary_embed = _make_embed_mock()
        self.list_embed = _make_embed_mock()

    def _make_score_service_mock(
        self, return_value=None, side_effect=None, proximity=None
    ):
        mock_score_service = AsyncMock()
        if side_effect is not None:
            mock_score_service.get_player_score.side_effect = side_effect
        else:
            mock_score_service.get_player_score.return_value = (
                return_value if return_value is not None else _make_breakdown()
            )
        mock_score_service.get_proximity_to_next_point = AsyncMock(
            return_value=(
                proximity if proximity is not None else _make_proximity_result()
            )
        )
        return mock_score_service

    def _make_clan_member_mocks(
        self, god_alignment=None
    ) -> tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
        """Wire up mocks for the clan-member branch.

        Returns (mock_get_score_service, mock_resolve_rank, mock_summary,
                 mock_list). mock_proximity is reachable via
        mock_get_score_service.return_value.get_proximity_to_next_point.
        """
        p_get_score_service = patch(
            "ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service"
        )
        mock_get_score_service = p_get_score_service.start()
        self.addCleanup(p_get_score_service.stop)
        mock_get_score_service.return_value = self._make_score_service_mock()

        p_resolve = patch(
            "ironforgedbot.commands.hiscore.cmd_point_progress._resolve_rank_display",
            return_value=(":test_rank:", discord.Color.greyple(), god_alignment),
        )
        mock_resolve_rank = p_resolve.start()
        self.addCleanup(p_resolve.stop)

        p_rank = patch(
            "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points",
            return_value=RANK.IRON,
        )
        p_rank.start()
        self.addCleanup(p_rank.stop)

        p_summary = patch(
            "ironforgedbot.commands.hiscore.cmd_point_progress._build_summary_embed",
            return_value=self.summary_embed,
        )
        mock_summary = p_summary.start()
        self.addCleanup(p_summary.stop)

        p_list = patch(
            "ironforgedbot.commands.hiscore.cmd_point_progress._build_list_embed",
            return_value=self.list_embed,
        )
        mock_list = p_list.start()
        self.addCleanup(p_list.stop)

        return mock_get_score_service, mock_resolve_rank, mock_summary, mock_list

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_error_response")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    async def test_cmd_point_progress_validation_error(
        self, mock_validate, mock_send_error
    ):
        mock_validate.side_effect = Exception("Invalid player name")

        await cmd_point_progress(self.interaction, "BadName")

        mock_send_error.assert_called_once_with(
            self.interaction, "Invalid player name", report_to_channel=False
        )

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_error_response")
    async def test_cmd_point_progress_hiscores_error(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresError("API Error")
        )

        await cmd_point_progress(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_error_response")
    async def test_cmd_point_progress_http_exception(
        self, mock_send_error, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HttpException("Network Error")
        )

        await cmd_point_progress(self.interaction, "TestUser")

        mock_send_error.assert_called_once_with(
            self.interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.send_member_no_hiscore_values"
    )
    async def test_cmd_point_progress_member_no_hiscores(
        self,
        mock_send_no_hiscore,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresNotFound("No hiscores found")
        )

        await cmd_point_progress(self.interaction, "TestUser")

        mock_send_no_hiscore.assert_called_once_with(
            self.interaction, self.test_user.display_name
        )

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.send_member_no_hiscore_values"
    )
    async def test_cmd_point_progress_prospect_with_no_hiscores(
        self,
        mock_send_no_hiscore,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.prospect_user, "ProspectUser")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresNotFound("No hiscores found")
        )

        await cmd_point_progress(self.interaction, "ProspectUser")

        mock_send_no_hiscore.assert_called_once_with(
            self.interaction, self.prospect_user.display_name
        )

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_not_clan_member")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    async def test_cmd_point_progress_non_member_hiscores_not_found(
        self,
        mock_get_color,
        mock_send_not_clan,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (None, "NonMember")
        mock_get_color.return_value = discord.Color.greyple()
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresNotFound("No hiscores found")
        )

        await cmd_point_progress(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()
        args, _ = mock_send_not_clan.call_args
        self.assertEqual(args[0], self.interaction)
        self.assertEqual(args[5], "NonMember")
        self.assertEqual(args[4], 0)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_prospect_response")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    async def test_cmd_point_progress_prospect_response(
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
        mock_find_emoji.return_value = ":iron:"
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "ProspectUser")

        mock_send_prospect.assert_called_once()
        args, _ = mock_send_prospect.call_args
        self.assertEqual(args[0], self.interaction)
        self.assertEqual(args[3], self.prospect_user)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_not_clan_member")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    async def test_cmd_point_progress_not_clan_member_response(
        self,
        mock_find_emoji,
        mock_get_color,
        mock_send_not_clan,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        non_member = create_test_member("NonMember", [], "NonMember")
        mock_validate.return_value = (non_member, "NonMember")
        mock_has_prospect_role.return_value = False
        mock_find_emoji.return_value = ":iron:"
        mock_get_color.return_value = discord.Color.greyple()
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()
        args, _ = mock_send_not_clan.call_args
        self.assertEqual(args[0], self.interaction)
        self.assertEqual(args[5], "NonMember")

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    async def test_cmd_point_progress_sends_two_embeds(
        self, mock_http, mock_validate, mock_has_prospect_role
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_has_prospect_role.return_value = False

        (
            mock_get_score_service,
            mock_resolve_rank,
            mock_summary,
            mock_list,
        ) = self._make_clan_member_mocks()

        await cmd_point_progress(self.interaction, "TestUser")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
        mock_get_score_service.return_value.get_player_score.assert_called_once_with(
            "TestUser"
        )
        mock_proximity = mock_get_score_service.return_value.get_proximity_to_next_point
        mock_proximity.assert_called_once()
        proximity_args, proximity_kwargs = mock_proximity.call_args
        self.assertIsInstance(proximity_args[0], ScoreBreakdown)
        self.assertEqual(proximity_kwargs.get("limit"), _TOP_N)

        mock_resolve_rank.assert_called_once_with(self.test_user, 14, RANK.IRON)

        mock_summary.assert_called_once()
        summary_kwargs = mock_summary.call_args.kwargs
        self.assertEqual(summary_kwargs["display_name"], self.test_user.display_name)
        self.assertEqual(summary_kwargs["rank_name"], RANK.IRON)
        self.assertEqual(summary_kwargs["points_total"], 14)
        self.assertIsNone(summary_kwargs["god_alignment"])

        mock_list.assert_called_once()

        self.interaction.followup.send.assert_called_once()
        send_kwargs = self.interaction.followup.send.call_args[1]
        self.assertIn("embeds", send_kwargs)
        self.assertEqual(len(send_kwargs["embeds"]), 2)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    async def test_cmd_point_progress_passes_god_alignment_to_summary(
        self, mock_http, mock_validate, mock_has_prospect_role
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_has_prospect_role.return_value = False

        (
            _,
            _,
            mock_summary,
            _,
        ) = self._make_clan_member_mocks(god_alignment=GOD_ALIGNMENT.SARADOMIN)

        await cmd_point_progress(self.interaction, "TestUser")

        summary_kwargs = mock_summary.call_args.kwargs
        self.assertEqual(summary_kwargs["god_alignment"], GOD_ALIGNMENT.SARADOMIN)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    async def test_cmd_point_progress_default_player_self(
        self, mock_http, mock_validate, mock_has_prospect_role
    ):
        mock_has_prospect_role.return_value = False
        mock_validate.return_value = (self.test_user, "TestUser")

        (
            mock_get_score_service,
            _,
            _,
            _,
        ) = self._make_clan_member_mocks()

        await cmd_point_progress(self.interaction, None)

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
        mock_get_score_service.return_value.get_player_score.assert_called_once_with(
            "TestUser"
        )
