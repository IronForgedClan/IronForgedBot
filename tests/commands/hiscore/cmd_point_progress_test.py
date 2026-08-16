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
            },
            {
                "name": "Defence",
                "display_order": 7,
                "emoji_key": "Defence",
                "xp_per_point": 100000,
                "xp_per_point_post_99": 300000,
            },
        ],
        clues=[
            {
                "name": "Clue Scrolls (beginner)",
                "display_name": "Beginner",
                "display_order": 1,
                "emoji_key": "Beginner_Clue",
                "kc_per_point": 10,
            },
        ],
        raids=[
            {
                "name": "Chambers of Xeric",
                "display_order": 1,
                "emoji_key": "Chambers_of_Xeric",
                "kc_per_point": 0.8,
            },
        ],
        bosses=[
            {
                "name": "Zulrah",
                "display_order": 59,
                "emoji_key": "Zulrah",
                "kc_per_point": 12,
            },
        ],
    )


with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    with patch(
        "ironforgedbot.common.logging_utils.log_command_execution",
        lambda *a, **kw: lambda f: f,
    ):
        from ironforgedbot.commands.hiscore.cmd_point_progress import cmd_point_progress


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
        ),
    ]


def _summary_patches(
    mock_get_color,
    mock_get_rank,
    mock_find_emoji,
    mock_build_embed,
    mock_get_next_rank,
    mock_get_god_alignment,
    summary_embed,
    list_embed,
    mock_render_percentage,
    rank=RANK.IRON,
    god_alignment=None,
):
    mock_get_rank.return_value = rank
    mock_get_color.return_value = discord.Color.greyple()
    mock_find_emoji.return_value = "<:emoji:123>"
    mock_build_embed.side_effect = [summary_embed, list_embed]
    mock_get_next_rank.return_value = RANK.MITHRIL
    mock_get_god_alignment.return_value = god_alignment
    mock_render_percentage.side_effect = lambda p, w: f"{round(p * 100)}%"


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
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_not_clan_member")
    async def test_cmd_point_progress_non_member_hiscores_not_found(
        self, mock_send_not_clan, mock_validate, mock_http, mock_get_score_service
    ):
        mock_validate.return_value = (None, "NonMember")
        mock_get_score_service.return_value = self._make_score_service_mock(
            side_effect=HiscoresNotFound("No hiscores found")
        )

        await cmd_point_progress(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

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
        mock_find_emoji.return_value = ":prospect:"
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "ProspectUser")

        mock_send_prospect.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.send_not_clan_member")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    async def test_cmd_point_progress_not_clan_member_response(
        self,
        mock_find_emoji,
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
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "NonMember")

        mock_send_not_clan.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_cmd_point_progress_sends_two_embeds(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        _summary_patches(
            mock_get_color,
            mock_get_rank,
            mock_find_emoji,
            mock_build_embed,
            mock_get_next_rank,
            mock_get_god_alignment,
            self.summary_embed,
            self.list_embed,
            mock_render_percentage,
        )
        mock_has_prospect_role.return_value = False
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "TestUser")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
        mock_get_score_service.return_value.get_player_score.assert_called_once_with(
            "TestUser"
        )
        mock_get_score_service.return_value.get_proximity_to_next_point.assert_called_once()

        self.interaction.followup.send.assert_called_once()
        send_kwargs = self.interaction.followup.send.call_args[1]
        self.assertIn("embeds", send_kwargs)
        self.assertEqual(len(send_kwargs["embeds"]), 2)

        self.assertEqual(mock_build_embed.call_count, 2)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_summary_embed_includes_member_rsn_rank_and_points(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        _summary_patches(
            mock_get_color,
            mock_get_rank,
            mock_find_emoji,
            mock_build_embed,
            mock_get_next_rank,
            mock_get_god_alignment,
            self.summary_embed,
            self.list_embed,
            mock_render_percentage,
        )
        mock_has_prospect_role.return_value = False
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "TestUser")

        field_names = {f.name for f in self.summary_embed.fields if f.name}
        self.assertIn("Member", field_names)
        self.assertIn("RSN", field_names)
        self.assertIn("Current Rank", field_names)
        self.assertIn("Total Points", field_names)
        self.assertIn("Points to Next Rank", field_names)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_summary_embed_god_rank_shows_alignment(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        _summary_patches(
            mock_get_color,
            mock_get_rank,
            mock_find_emoji,
            mock_build_embed,
            mock_get_next_rank,
            mock_get_god_alignment,
            self.summary_embed,
            self.list_embed,
            mock_render_percentage,
            rank=RANK.GOD,
            god_alignment=GOD_ALIGNMENT.SARADOMIN,
        )
        mock_has_prospect_role.return_value = False
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, "TestUser")

        field_names = {f.name for f in self.summary_embed.fields if f.name}
        self.assertIn("God Alignment", field_names)
        self.assertNotIn("Points to Next Rank", field_names)

        god_field = next(
            f for f in self.summary_embed.fields if f.name == "God Alignment"
        )
        self.assertIn("Saradomin", god_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_list_embed_uses_render_percentage(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_render_percentage.side_effect = lambda p, w: (
            ">99%" if p >= 1.0 else ("<1%" if p < 0.01 else f"{round(p * 100)}%")
        )
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = "<:emoji:123>"
        mock_build_embed.side_effect = [self.summary_embed, self.list_embed]
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_god_alignment.return_value = None
        mock_has_prospect_role.return_value = False

        proximity_with_hundo = [
            NextPointProgress(
                category="skill",
                name="Defence",
                display_name=None,
                emoji_key="Defence",
                current=300000,
                points=3,
                progress_percent=1.0,
                remaining_to_next=0,
                unit="xp",
            ),
        ]
        mock_get_score_service.return_value = self._make_score_service_mock(
            proximity=proximity_with_hundo
        )

        await cmd_point_progress(self.interaction, "TestUser")

        mock_render_percentage.assert_called()
        first_list_field = next(f for f in self.list_embed.fields if f.name)
        self.assertIn(">99%", first_list_field.name)
        self.assertNotIn("100%", first_list_field.name)
        self.assertIn("300,000xp/300,000xp", first_list_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_list_embed_no_scientific_notation_for_large_xp(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_render_percentage.return_value = "84%"
        mock_get_rank.return_value = RANK.IRON
        mock_get_color.return_value = discord.Color.greyple()
        mock_find_emoji.return_value = "<:emoji:123>"
        mock_build_embed.side_effect = [self.summary_embed, self.list_embed]
        mock_get_next_rank.return_value = RANK.MITHRIL
        mock_get_god_alignment.return_value = None
        mock_has_prospect_role.return_value = False

        large_xp = [
            NextPointProgress(
                category="skill",
                name="Attack",
                display_name=None,
                emoji_key="Attack",
                current=17_483_000,
                points=130,
                progress_percent=0.84,
                remaining_to_next=3_940,
                unit="xp",
            ),
        ]
        mock_get_score_service.return_value = self._make_score_service_mock(
            proximity=large_xp
        )

        await cmd_point_progress(self.interaction, "TestUser")

        first_list_field = next(f for f in self.list_embed.fields if f.name)
        self.assertNotIn("e+", first_list_field.value)
        self.assertNotIn("e-", first_list_field.value)
        self.assertIn("17,483,000xp/17,486,940xp", first_list_field.value)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_cmd_point_progress_empty_proximity(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        _summary_patches(
            mock_get_color,
            mock_get_rank,
            mock_find_emoji,
            mock_build_embed,
            mock_get_next_rank,
            mock_get_god_alignment,
            self.summary_embed,
            self.list_embed,
            mock_render_percentage,
        )
        mock_has_prospect_role.return_value = False
        mock_get_score_service.return_value = self._make_score_service_mock(
            proximity=[]
        )

        await cmd_point_progress(self.interaction, "TestUser")

        self.interaction.followup.send.assert_called_once()
        real_fields = [f for f in self.list_embed.fields if f.name]
        self.assertEqual(len(real_fields), 1)
        self.assertEqual(real_fields[0].name, "No progress yet")
        self.assertFalse(real_fields[0].inline)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_cmd_point_progress_caps_at_ten_fields(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        _summary_patches(
            mock_get_color,
            mock_get_rank,
            mock_find_emoji,
            mock_build_embed,
            mock_get_next_rank,
            mock_get_god_alignment,
            self.summary_embed,
            self.list_embed,
            mock_render_percentage,
        )
        mock_has_prospect_role.return_value = False
        proximity = [
            NextPointProgress(
                category="boss",
                name=f"Boss{i}",
                display_name=None,
                emoji_key=f"Boss{i}",
                current=10,
                points=i,
                progress_percent=0.5 - (i * 0.01),
                remaining_to_next=10,
                unit="kc",
            )
            for i in range(15)
        ]
        mock_get_score_service.return_value = self._make_score_service_mock(
            proximity=proximity
        )

        await cmd_point_progress(self.interaction, "TestUser")

        real_fields = [f for f in self.list_embed.fields if f.name]
        self.assertEqual(len(real_fields), 15)

    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_score_service")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.HTTP")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.validate_playername")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.has_prospect_role")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_from_points")
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_rank_color_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_next_rank_from_points"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.get_god_alignment_from_member"
    )
    @patch(
        "ironforgedbot.commands.hiscore.cmd_point_progress.RANK_POINTS",
        {"IRON": 0, "MITHRIL": 100},
    )
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.find_emoji")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.build_response_embed")
    @patch("ironforgedbot.commands.hiscore.cmd_point_progress.render_percentage")
    async def test_cmd_point_progress_default_player_self(
        self,
        mock_render_percentage,
        mock_build_embed,
        mock_find_emoji,
        mock_get_god_alignment,
        mock_get_next_rank,
        mock_get_color,
        mock_get_rank,
        mock_has_prospect_role,
        mock_validate,
        mock_http,
        mock_get_score_service,
    ):
        mock_validate.return_value = (self.test_user, "TestUser")
        _summary_patches(
            mock_get_color,
            mock_get_rank,
            mock_find_emoji,
            mock_build_embed,
            mock_get_next_rank,
            mock_get_god_alignment,
            self.summary_embed,
            self.list_embed,
            mock_render_percentage,
        )
        mock_has_prospect_role.return_value = False
        mock_get_score_service.return_value = self._make_score_service_mock()

        await cmd_point_progress(self.interaction, None)

        mock_validate.assert_called_once_with(
            self.interaction.guild, "TestUser", must_be_member=False
        )
