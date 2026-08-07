import logging

import discord
from discord import app_commands

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import find_emoji, validate_playername
from ironforgedcore.common.normalize import normalize_discord_string
from ironforgedcore.common.ranks import get_rank_from_points
from ironforgedbot.common.ranks_discord import get_rank_color_from_points
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

_TOP_N = 10
_EMBED_TITLE = "🎯 Point Progress — Top 10 Closest"
_EMBED_DESCRIPTION = (
    "Skills, bosses, raids, and clues ranked by how close you are to "
    "earning your next point. Items with no progress are hidden."
)


def _format_remaining(progress: NextPointProgress) -> str:
    remaining = progress.remaining_to_next
    unit = progress.unit
    if progress.unit == "kc" and not isinstance(remaining, int):
        return f"{remaining:.1f} {unit}"
    return f"{remaining:,} {unit}"


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
    proximity = await service.get_proximity_to_next_point(data)

    embed = build_response_embed(_EMBED_TITLE, _EMBED_DESCRIPTION, rank_color)

    if not proximity:
        embed.add_field(
            name="No progress yet",
            value=(
                f"{EMPTY_SPACE}This player has no qualifying XP or KC yet. "
                "Start grinding to populate the list."
            ),
            inline=False,
        )
    else:
        for progress in proximity[:_TOP_N]:
            label = progress.display_name or progress.name
            icon = find_emoji(progress.emoji_key)
            embed.add_field(
                name=f"{icon} {label}",
                value=(
                    f"{EMPTY_SPACE}{progress.progress_percent:.0%} • "
                    f"{_format_remaining(progress)} • "
                    f"{progress.points:,} pts"
                ),
                inline=True,
            )
        while len(embed.fields) % 3 != 0:
            embed.add_field(name="", value="", inline=True)

    await interaction.followup.send(embed=embed)
