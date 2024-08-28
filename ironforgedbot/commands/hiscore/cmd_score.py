import logging
from typing import Optional

import discord

from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_emoji,
    validate_playername,
)
from ironforgedbot.common.ranks import (
    RANK_POINTS,
    RANKS,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role

logger = logging.getLogger(__name__)


@require_role(ROLES.ANY)
async def cmd_score(interaction: discord.Interaction, player: Optional[str]):
    """Compute clan score for a Runescape player name.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Player to display score for.
    """
    if player is None:
        player = interaction.user.display_name

    try:
        member, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    try:
        data = score_info(player)
    except RuntimeError as error:
        await send_error_response(interaction, str(error))
        return

    activities = data.clues + data.raids + data.bosses

    skill_points = 0
    for skill in data.skills:
        skill_points += skill["points"]

    activity_points = 0
    for activity in activities:
        activity_points += activity["points"]

    points_total = skill_points + activity_points
    rank_name = get_rank_from_points(points_total)
    rank_color = get_rank_color_from_points(points_total)
    rank_icon = find_emoji(interaction, rank_name)

    next_rank_name = get_next_rank_from_points(points_total)
    next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()].value
    next_rank_icon = find_emoji(interaction, next_rank_name)

    embed = build_response_embed(f"{rank_icon} {member.display_name}", "", rank_color)
    embed.add_field(
        name="Skill Points",
        value=f"{skill_points:,} ({calculate_percentage(skill_points, points_total)}%)",
        inline=True,
    )
    embed.add_field(
        name="Activity Points",
        value=f"{activity_points:,} ({calculate_percentage(activity_points, points_total)}%)",
        inline=True,
    )
    embed.add_field(name="", value="", inline=False)
    embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
    embed.add_field(name="Rank", value=f"{rank_icon} {rank_name}", inline=True)

    if rank_name == RANKS.MYTH.value:
        grass_emoji = find_emoji(interaction, "grass")
        embed.add_field(
            name="",
            value=(
                f"{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}"
                f"{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}"
            ),
            inline=False,
        )
    else:
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="Rank Progress",
            value=(
                f"{rank_icon} -> {next_rank_icon} {points_total}/{next_rank_point_threshold} "
                f"({calculate_percentage(points_total, next_rank_point_threshold)}%)"
            ),
            inline=False,
        )

    await interaction.followup.send(embed=embed)
