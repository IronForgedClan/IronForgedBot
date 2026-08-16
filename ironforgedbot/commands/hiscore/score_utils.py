import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.ranks_discord import (
    get_god_alignment_from_member,
    get_rank_color_from_points,
)
from ironforgedcore.common.ranks import RANK
from ironforgedcore.models.score import ScoreBreakdown


def _calculate_points(data: ScoreBreakdown) -> tuple[int, int, int]:
    """Sum skill and activity points from a score breakdown.

    Returns:
        (skill_points, activity_points, points_total)
    """
    skill_points = sum(s.points for s in data.skills)
    activity_points = sum(a.points for a in (data.clues + data.raids + data.bosses))
    return skill_points, activity_points, skill_points + activity_points


def _resolve_rank_display(
    member: discord.Member | None,
    points_total: int,
    rank_name: str,
) -> tuple[str, discord.Color, str | None]:
    """Resolve rank icon, embed color, and god alignment for a player.

    Args:
        member: The Discord member, or None if not in the clan.
        points_total: The player's total points.
        rank_name: The player's current rank name.

    Returns:
        Tuple of (rank_icon, rank_color, god_alignment).
        god_alignment is None for non-GOD ranks.
    """
    if rank_name == RANK.GOD:
        god_alignment = get_god_alignment_from_member(member)
        rank_color = get_rank_color_from_points(points_total, god_alignment)
        rank_icon = find_emoji(god_alignment or rank_name)
        return rank_icon, rank_color, god_alignment
    return find_emoji(rank_name), get_rank_color_from_points(points_total), None
