import logging

import discord
from discord import app_commands

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.helpers import (
    find_emoji,
    normalize_discord_string,
    render_percentage,
    validate_playername,
)
from ironforgedbot.common.ranks import (
    GOD_ALIGNMENT,
    RANK,
    RANK_POINTS,
    get_god_alignment_from_member,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.commands.hiscore.score_utils import _calculate_points
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
    send_member_no_hiscore_values,
    send_not_clan_member,
    send_prospect_response,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role, has_prospect_role
from ironforgedbot.config import CONFIG
from ironforgedbot.database.database import db
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.http import HTTP, HttpException
from ironforgedbot.models.score import ScoreBreakdown
from ironforgedbot.services.score_history_service import ScoreHistoryService
from ironforgedbot.services.score_service import get_score_service

logger = logging.getLogger(__name__)

_SCORE_PROGRESS_PERIODS = [7, 14, 30]
_PROGRESS_BAR_LENGTH = 20
_PROGRESS_BAR_FILLED = "▰"
_PROGRESS_BAR_EMPTY = "▱"

_SCORE_EMBED_DESCRIPTION = (
    "Points are earned through in-game achievements and determine your clan rank. "
    "Use the `breakdown` command to view a detailed breakdown of earned points. "
    f"See <#{CONFIG.RANKINGS_CHANNEL_ID}> for more information."
)


def _build_rank_progress_bar(
    points_total: int,
    rank_point_threshold: int,
    next_rank_point_threshold: int,
    rank_icon: str,
    next_rank_icon: str,
) -> str:
    """Build a visual progress bar string showing progress toward the next rank.

    Args:
        points_total: The member's current score.
        rank_point_threshold: The point threshold for the current rank.
        next_rank_point_threshold: The point threshold for the next rank.
        rank_icon: Emoji for the current rank.
        next_rank_icon: Emoji for the next rank.
    """
    span = next_rank_point_threshold - rank_point_threshold
    progress = points_total - rank_point_threshold
    ratio = max(0.0, min(1.0, progress / span)) if span > 0 else 1.0
    filled = round(ratio * _PROGRESS_BAR_LENGTH)
    bar = _PROGRESS_BAR_FILLED * filled + _PROGRESS_BAR_EMPTY * (
        _PROGRESS_BAR_LENGTH - filled
    )
    percentage = render_percentage(progress, span)
    return f"{rank_icon} {bar} {next_rank_icon}" f" ({percentage})"



async def _get_score_history(discord_id: int, current_score: int) -> dict[int, int]:
    """Return score deltas for each history period that has a snapshot.

    Queries the nearest score snapshot for each period (7d, 14d, 30d) and
    returns a dict mapping days -> delta for each period that has data.
    Returns an empty dict if no historical data is available or on error.

    Args:
        discord_id: The Discord ID of the member.
        current_score: The member's current computed score.
    """
    try:
        async with db.get_session() as session:
            service = ScoreHistoryService(session)
            progress = await service.get_score_history(
                discord_id, _SCORE_PROGRESS_PERIODS
            )
    except Exception:
        return {}

    result = {}
    for days in _SCORE_PROGRESS_PERIODS:
        snapshot = progress.get(days)
        if snapshot is not None:
            result[days] = current_score - snapshot

    return result


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to display score for (defaults to your nickname)"
)
async def cmd_score(interaction: discord.Interaction, player: str | None = None):
    """Compute clan score for a Runescape player name.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Player to display score for.
    """
    if player is None:
        player = interaction.user.display_name

    assert interaction.guild

    try:
        member, player = validate_playername(
            interaction.guild, player, must_be_member=False
        )
    except Exception as e:
        return await send_error_response(interaction, str(e), report_to_channel=False)

    display_name = member.display_name if member is not None else player

    try:
        service = get_score_service(HTTP)
        data = await service.get_player_score(player)
    except (HiscoresError, HttpException):
        return await send_error_response(
            interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )
    except HiscoresNotFound:
        if member:
            return await send_member_no_hiscore_values(interaction, display_name)
        else:
            data = ScoreBreakdown([], [], [], [])

    skill_points, activity_points, points_total = _calculate_points(data)
    rank_name = get_rank_from_points(points_total)

    # Variables only used for non-GOD ranks; initialized to None to make scoping explicit.
    rank_point_threshold: int | None = None
    next_rank_name: str | None = None
    next_rank_point_threshold: int | None = None
    next_rank_icon: str | None = None

    god_alignment = None
    god_rank_icon: str | None = None
    if rank_name == RANK.GOD:
        god_alignment = get_god_alignment_from_member(member)
        rank_color = get_rank_color_from_points(points_total, god_alignment)
        rank_icon = find_emoji(god_alignment or rank_name)
        god_rank_icon = find_emoji(RANK.GOD)
    else:
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(rank_name)
        rank_point_threshold = RANK_POINTS[rank_name.upper()]
        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()]
        next_rank_icon = find_emoji(next_rank_name)

    if member and member.roles:
        if has_prospect_role(member):
            return await send_prospect_response(
                interaction, rank_name, rank_icon, member
            )

    if not member or not check_member_has_role(member, ROLE.MEMBER):
        return await send_not_clan_member(
            interaction, rank_name, rank_icon, rank_color, points_total, display_name
        )

    embed = build_response_embed(
        "🏆 Member Score",
        _SCORE_EMBED_DESCRIPTION,
        rank_color,
    )

    member_icon = find_emoji("Grass") if rank_name == RANK.GOD else rank_icon
    embed.add_field(
        name="Member",
        value=f"{member_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )
    embed.add_field(
        name="Current Rank",
        value=f"{god_rank_icon if god_rank_icon else rank_icon} {rank_name}",
        inline=True,
    )

    if rank_name == RANK.GOD:
        alignment_value = (
            f"{find_emoji(god_alignment)} {god_alignment}"
            if god_alignment
            else "_Unaligned_"
        )
        embed.add_field(name="God Alignment", value=alignment_value, inline=True)
    else:
        points_needed = next_rank_point_threshold - points_total
        embed.add_field(
            name="Next Rank",
            value=f"{next_rank_icon} {next_rank_name} (in {points_needed:,} pts)",
            inline=True,
        )

    embed.add_field(
        name="Total Points",
        value=f"{points_total:,}",
        inline=True,
    )
    embed.add_field(
        name="Skill Points",
        value=f"{skill_points:,} ({render_percentage(skill_points, points_total)})",
        inline=True,
    )
    embed.add_field(
        name="Activity Points",
        value=f"{activity_points:,} ({render_percentage(activity_points, points_total)})",
        inline=True,
    )

    score_history = await _get_score_history(member.id, points_total)
    if score_history:
        first = True
        for days in _SCORE_PROGRESS_PERIODS:
            delta = score_history.get(days)
            if delta is None:
                continue
            embed.add_field(
                name="Score History" if first else EMPTY_SPACE,
                value=f"{delta:+,} ({days}d)",
                inline=True,
            )
            first = False

    if rank_name != RANK.GOD:
        progress_bar = _build_rank_progress_bar(
            points_total,
            rank_point_threshold,
            next_rank_point_threshold,
            rank_icon,
            next_rank_icon,
        )
        embed.add_field(
            name="Rank Progress",
            value=progress_bar,
            inline=False,
        )

    await interaction.followup.send(embed=embed)
