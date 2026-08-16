import unittest
from unittest.mock import patch

import discord

from ironforgedbot.commands.hiscore.score_utils import (
    _calculate_points,
    _resolve_rank_display,
)
from tests.helpers import create_test_member
from ironforgedcore.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedcore.common.roles import ROLE
from ironforgedcore.models.score import ActivityScore, ScoreBreakdown, SkillScore


class TestCalculatePoints(unittest.TestCase):
    def test_calculate_points_all_categories(self):
        data = ScoreBreakdown(
            skills=[SkillScore("Attack", None, 1, "Attack", 1000, 99, 300)],
            clues=[ActivityScore("Easy", None, 1, "Easy", 10, 50)],
            raids=[ActivityScore("CoX", None, 1, "CoX", 5, 100)],
            bosses=[ActivityScore("Zulrah", None, 1, "Zulrah", 50, 200)],
        )
        skill_points, activity_points, points_total = _calculate_points(data)

        self.assertEqual(skill_points, 300)
        self.assertEqual(activity_points, 350)
        self.assertEqual(points_total, 650)

    def test_calculate_points_skills_only(self):
        data = ScoreBreakdown(
            skills=[
                SkillScore("Attack", None, 1, "Attack", 1000, 99, 100),
                SkillScore("Strength", None, 2, "Strength", 2000, 99, 200),
            ],
            clues=[],
            raids=[],
            bosses=[],
        )
        skill_points, activity_points, points_total = _calculate_points(data)

        self.assertEqual(skill_points, 300)
        self.assertEqual(activity_points, 0)
        self.assertEqual(points_total, 300)

    def test_calculate_points_activities_only(self):
        data = ScoreBreakdown(
            skills=[],
            clues=[ActivityScore("Easy", None, 1, "Easy", 10, 50)],
            raids=[ActivityScore("CoX", None, 1, "CoX", 5, 75)],
            bosses=[ActivityScore("Zulrah", None, 1, "Zulrah", 50, 25)],
        )
        skill_points, activity_points, points_total = _calculate_points(data)

        self.assertEqual(skill_points, 0)
        self.assertEqual(activity_points, 150)
        self.assertEqual(points_total, 150)

    def test_calculate_points_empty_breakdown(self):
        data = ScoreBreakdown(skills=[], clues=[], raids=[], bosses=[])
        skill_points, activity_points, points_total = _calculate_points(data)

        self.assertEqual(skill_points, 0)
        self.assertEqual(activity_points, 0)
        self.assertEqual(points_total, 0)

    def test_calculate_points_multiple_skills(self):
        data = ScoreBreakdown(
            skills=[
                SkillScore("Attack", None, 1, "Attack", 1000, 99, 100),
                SkillScore("Strength", None, 2, "Strength", 2000, 99, 200),
                SkillScore("Defence", None, 3, "Defence", 500, 70, 50),
            ],
            clues=[],
            raids=[],
            bosses=[],
        )
        skill_points, activity_points, points_total = _calculate_points(data)

        self.assertEqual(skill_points, 350)
        self.assertEqual(points_total, 350)

    def test_calculate_points_returns_correct_tuple_order(self):
        data = ScoreBreakdown(
            skills=[SkillScore("Attack", None, 1, "Attack", 1000, 99, 10)],
            clues=[ActivityScore("Easy", None, 1, "Easy", 5, 20)],
            raids=[],
            bosses=[],
        )
        result = _calculate_points(data)

        self.assertEqual(len(result), 3)
        skill_points, activity_points, points_total = result
        self.assertEqual(skill_points, 10)
        self.assertEqual(activity_points, 20)
        self.assertEqual(points_total, 30)


class TestResolveRankDisplay(unittest.TestCase):
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.find_emoji",
        return_value=":saradomin:",
    )
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.get_god_alignment_from_member",
        return_value=GOD_ALIGNMENT.SARADOMIN,
    )
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.get_rank_color_from_points",
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
        "ironforgedbot.commands.hiscore.score_utils.find_emoji", return_value=":god:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.get_god_alignment_from_member",
        return_value=None,
    )
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.get_rank_color_from_points",
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
        "ironforgedbot.commands.hiscore.score_utils.find_emoji", return_value=":iron:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.get_rank_color_from_points",
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
        "ironforgedbot.commands.hiscore.score_utils.find_emoji", return_value=":iron:"
    )
    @patch(
        "ironforgedbot.commands.hiscore.score_utils.get_rank_color_from_points",
        return_value=discord.Color.greyple(),
    )
    def test_none_member_non_god_rank(self, mock_color, mock_emoji):
        rank_icon, rank_color, god_alignment = _resolve_rank_display(None, 0, RANK.IRON)

        self.assertIsNone(god_alignment)
        self.assertEqual(rank_icon, ":iron:")
