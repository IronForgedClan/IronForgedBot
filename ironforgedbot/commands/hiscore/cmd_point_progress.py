import logging
import math

import discord
from discord import app_commands

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import find_emoji, validate_playername
from ironforgedcore.common.normalize import normalize_discord_string
from ironforgedcore.common.numbers import render_percentage
from ironforgedcore.common.ranks import (
    RANK,
    RANK_POINTS,
    get_next_rank_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.ranks_discord import (
    get_god_alignment_from_member,
    get_rank_color_from_points,
)
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
    send_member_no_hiscore_values,
    send_not_clan_member,
    send_prospect_response,
)
from ironforgedcore.common.roles import ROLE
from ironforgedbot.common.roles_discord import check_member_has_role, has_prospect_role
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.decorators.require_role import require_role
from ironforgedcore.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedcore.http import HTTP, HttpException
from ironforgedcore.models.score import NextPointProgress, ScoreBreakdown
from ironforgedcore.services.score_service import get_score_service

logger = logging.getLogger(__name__)

_TOP_N = 15
_EMBED_TITLE = "🎯 Point Progress"
_EMBED_DESCRIPTION = (
    "Skills, bosses, raids, and clues ranked by how close you are to "
    "earning your next point. Items with no progress are hidden."
)


def _build_summary_embed(
    display_name: str,
    rsn: str,
    rank_name: str,
    rank_icon: str,
    rank_color: discord.Color,
    god_alignment,
    points_total: int,
) -> discord.Embed:
    """Build the user-info summary embed (embed 1)."""
    member_icon = find_emoji("Grass") if rank_name == RANK.GOD else rank_icon
    embed = build_response_embed(
        f"{_EMBED_TITLE} — {display_name}", _EMBED_DESCRIPTION, rank_color
    )

    embed.add_field(
        name="Member",
        value=f"{member_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )
    embed.add_field(name="RSN", value=normalize_discord_string(rsn), inline=True)

    if rank_name == RANK.GOD:
        alignment_value = (
            f"{rank_icon} {god_alignment}"
            if god_alignment
            else f"{find_emoji('God')} Unaligned!"
        )
        embed.add_field(
            name="Current Rank",
            value=f"{rank_icon} {rank_name}",
            inline=True,
        )
        embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
        embed.add_field(name="God Alignment", value=alignment_value, inline=True)
        embed.add_field(name="", value="", inline=True)
    else:
        rank_point_threshold = RANK_POINTS[rank_name.upper()]
        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()]
        next_rank_icon = find_emoji(next_rank_name)
        points_needed = next_rank_point_threshold - points_total

        embed.add_field(
            name="Current Rank",
            value=f"{rank_icon} {rank_name}",
            inline=True,
        )
        embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
        embed.add_field(
            name="Points to Next Rank",
            value=f"{next_rank_icon} {next_rank_name} (in {points_needed:,} pts)",
            inline=True,
        )
        embed.add_field(name="", value="", inline=True)
        embed.add_field(name="", value="", inline=True)

    return embed


def _build_list_embed(
    proximity: list[NextPointProgress],
    rank_color: discord.Color,
) -> discord.Embed:
    """Build the top-10 list embed (embed 2)."""
    embed = build_response_embed("", "", rank_color)

    if not proximity:
        embed.add_field(
            name="No progress yet",
            value=(
                f"{EMPTY_SPACE}This player has no qualifying XP or KC yet. "
                "Start grinding to populate the list."
            ),
            inline=False,
        )
        return embed

    for progress in proximity[:_TOP_N]:
        icon = find_emoji(progress.emoji_key)
        pct = render_percentage(progress.progress_percent, 1.0)
        required = math.ceil(progress.current + progress.remaining_to_next)
        embed.add_field(
            name=f"{icon} {pct}",
            value=(
                f"{progress.current:,.0f}{progress.unit}/"
                f"{required:,.0f}{progress.unit}"
            ),
            inline=True,
        )
    while len(embed.fields) % 3 != 0:
        embed.add_field(name="", value="", inline=True)

    return embed


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to check point progress for (defaults to your nickname)"
)
async def cmd_point_progress(
    interaction: discord.Interaction, player: str | None = None
):
    """Show the top 10 skills/activities closest to gaining a point.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Player to check. Defaults to the invoking user.
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
    rsn = player

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
        data = ScoreBreakdown([], [], [], [])

    if member and member.roles:
        if has_prospect_role(member):
            skill_points, activity_points, points_total = (0, 0, 0)
            for skill in data.skills:
                skill_points += skill.points
            for activity in data.clues + data.raids + data.bosses:
                activity_points += activity.points
            points_total = skill_points + activity_points
            rank_name = get_rank_from_points(points_total)
            rank_icon = find_emoji(rank_name)
            return await send_prospect_response(
                interaction, rank_name, rank_icon, member
            )

    if not member or not check_member_has_role(member, ROLE.MEMBER):
        skill_points = sum(s.points for s in data.skills)
        activity_points = sum(a.points for a in (data.clues + data.raids + data.bosses))
        points_total = skill_points + activity_points
        rank_name = get_rank_from_points(points_total)
        rank_icon = find_emoji(rank_name)
        rank_color = get_rank_color_from_points(points_total)
        return await send_not_clan_member(
            interaction,
            rank_name,
            rank_icon,
            rank_color,
            points_total,
            display_name,
        )

    points_total = sum(s.points for s in data.skills) + sum(
        a.points for a in (data.clues + data.raids + data.bosses)
    )
    rank_name = get_rank_from_points(points_total)
    rank_color = get_rank_color_from_points(points_total)
    god_alignment = (
        get_god_alignment_from_member(member) if rank_name == RANK.GOD else None
    )
    rank_icon = find_emoji(god_alignment or rank_name)
    proximity = await service.get_proximity_to_next_point(data)

    summary_embed = _build_summary_embed(
        display_name=display_name,
        rsn=rsn,
        rank_name=rank_name,
        rank_icon=rank_icon,
        rank_color=rank_color,
        god_alignment=god_alignment,
        points_total=points_total,
    )
    list_embed = _build_list_embed(proximity, rank_color)

    await interaction.followup.send(embeds=[summary_embed, list_embed])
