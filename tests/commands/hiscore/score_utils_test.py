import unittest

from ironforgedbot.commands.hiscore.score_utils import _calculate_points
from ironforgedbot.models.score import ActivityScore, ScoreBreakdown, SkillScore


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
