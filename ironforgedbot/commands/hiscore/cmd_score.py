import logging
from typing import Optional

import discord

from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_emoji,
    normalize_discord_string,
    validate_playername,
)
from ironforgedbot.common.ranks import (
    GOD_ALIGNMENT,
    RANK_POINTS,
    RANKS,
    get_god_alignment_from_member,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.responses import build_response_embed, send_error_response

logger = logging.getLogger(__name__)


async def cmd_score(interaction: discord.Interaction, player: Optional[str]):
    """Compute clan score for a Runescape player name.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Player to display score for.
    """
    await interaction.response.defer(thinking=True)

    if player is None:
        player = interaction.user.display_name

    assert interaction.guild

    try:
        member, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    caller = normalize_discord_string(interaction.user.display_name)
    logger.info(f"Handling '/score player:{player}' on behalf of '{caller}'")

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

    if rank_name == RANKS.GOD:
        god_alignment = get_god_alignment_from_member(member)

        rank_color = get_rank_color_from_points(points_total, god_alignment)
        rank_icon = find_emoji(interaction, god_alignment or rank_name)
    else:
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(interaction, rank_name)
        rank_point_threshold = RANK_POINTS[rank_name.upper()]

        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()]
        next_rank_icon = find_emoji(interaction, next_rank_name)

    embed = build_response_embed(
        f"{rank_icon} {member.display_name} | Score: `{points_total:,}`", "", rank_color
    )
    embed.add_field(
        name="Skill Points",
        value=f"{skill_points:,} ({calculate_percentage(skill_points, points_total)})%",
        inline=True,
    )
    embed.add_field(
        name="Activity Points",
        value=f"{activity_points:,} ({calculate_percentage(activity_points, points_total)})%",
        inline=True,
    )

    if rank_name == RANKS.GOD:
        logging.info(f"trying to render god special for {god_alignment}")
        match god_alignment:
            case GOD_ALIGNMENT.SARADOMIN:
                alignment_emoji = ":pray:"
            case GOD_ALIGNMENT.ZAMORAK:
                alignment_emoji = ":fire:"
            case GOD_ALIGNMENT.GUTHIX:
                alignment_emoji = find_emoji(interaction, "grass")
            case _:
                alignment_emoji = ":nerd:"

        embed.add_field(
            name="",
            value=(
                f"{alignment_emoji}{EMPTY_SPACE}{alignment_emoji}{EMPTY_SPACE}{alignment_emoji}"
                f"{EMPTY_SPACE}{alignment_emoji}{EMPTY_SPACE}{alignment_emoji}{EMPTY_SPACE}{alignment_emoji}"
            ),
            inline=False,
        )
    else:
        embed.add_field(
            name="Rank Progress",
            value=(
                f"{rank_icon} → {next_rank_icon} {points_total}/{next_rank_point_threshold} "
                f"({calculate_percentage(points_total - int(rank_point_threshold), int(next_rank_point_threshold) - int(rank_point_threshold))}%)"
            ),
            inline=False,
        )

    await interaction.followup.send(embed=embed)
