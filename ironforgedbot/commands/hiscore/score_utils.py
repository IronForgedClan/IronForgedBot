from ironforgedbot.models.score import ScoreBreakdown


def _calculate_points(data: ScoreBreakdown) -> tuple[int, int, int]:
    """Sum skill and activity points from a score breakdown.

    Returns:
        (skill_points, activity_points, points_total)
    """
    skill_points = sum(s.points for s in data.skills)
    activity_points = sum(a.points for a in (data.clues + data.raids + data.bosses))
    return skill_points, activity_points, skill_points + activity_points
