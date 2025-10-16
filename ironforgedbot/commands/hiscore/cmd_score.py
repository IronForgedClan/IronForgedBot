import logging
from typing import Optional

import discord
from discord import app_commands

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.helpers import (
    find_emoji,
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
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
    send_member_no_hiscore_values,
    send_not_clan_member,
    send_prospect_response,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.decorators.decorators import require_role
from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.http import HTTP, HttpException
from ironforgedbot.models.score import ScoreBreakdown
from ironforgedbot.services.score_service import get_score_service

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to display score for (defaults to your nickname)"
)
async def cmd_score(interaction: discord.Interaction, player: Optional[str] = None):
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

    activities = data.clues + data.raids + data.bosses

    skill_points = 0
    for skill in data.skills:
        skill_points += skill.points

    activity_points = 0
    for activity in activities:
        activity_points += activity.points

    points_total = skill_points + activity_points
    rank_name = get_rank_from_points(points_total)

    god_alignment = None
    if rank_name == RANK.GOD:
        god_alignment = get_god_alignment_from_member(member)

        rank_color = get_rank_color_from_points(points_total, god_alignment)
        rank_icon = find_emoji(god_alignment or rank_name)
    else:
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(rank_name)
        rank_point_threshold = RANK_POINTS[rank_name.upper()]

        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()]
        next_rank_icon = find_emoji(next_rank_name)

    if member and member.roles:
        if check_member_has_role(member, ROLE.PROSPECT):
            return await send_prospect_response(
                interaction, rank_name, rank_icon, member
            )

    if not member or not check_member_has_role(member, ROLE.MEMBER):
        return await send_not_clan_member(
            interaction, rank_name, rank_icon, rank_color, points_total, display_name
        )

    embed = build_response_embed(
        f"{rank_icon} {display_name} | Score: {points_total:,}",
        "",
        rank_color,
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

    if rank_name == RANK.GOD:
        match god_alignment:
            case GOD_ALIGNMENT.SARADOMIN:
                icon = find_emoji("Saradomin")
                alignment_emojis = f"{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}"
            case GOD_ALIGNMENT.ZAMORAK:
                icon = find_emoji("Zamorak")
                alignment_emojis = f"{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}"
            case GOD_ALIGNMENT.GUTHIX:
                icon = find_emoji("Guthix")
                alignment_emojis = f"{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}"
            case _:
                icon = find_emoji("grass")
                alignment_emojis = (
                    f"{icon}:nerd:{icon}:nerd:{icon}:nerd:{icon}:nerd:{icon}"
                )

        embed.add_field(
            name="",
            value=f"{alignment_emojis}",
            inline=False,
        )
    else:
        percentage = render_percentage(
            points_total - int(rank_point_threshold),
            int(next_rank_point_threshold) - int(rank_point_threshold),
        )
        embed.add_field(
            name="Rank Progress",
            value=(
                f"{rank_icon} → {next_rank_icon} {points_total:,}/{next_rank_point_threshold:,} ({percentage})"
            ),
            inline=False,
        )

    await interaction.followup.send(embed=embed)
