import logging
from typing import Optional

import discord

from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import (
    find_emoji,
    render_percentage,
    validate_playername,
)
from ironforgedbot.common.ranks import (
    GOD_ALIGNMENT,
    RANK_POINTS,
    RANK,
    get_god_alignment_from_member,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
    send_member_no_hiscore_values,
    send_prospect_response,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.decorators import require_role

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
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
        return await send_error_response(interaction, str(e))

    display_name = member.display_name if member is not None else player

    try:
        data = await score_info(player)
    except RuntimeError as error:
        await send_error_response(interaction, str(error))
        return

    if not data:
        return await send_member_no_hiscore_values(interaction, display_name)

    activities = data.clues + data.raids + data.bosses

    skill_points = 0
    for skill in data.skills:
        skill_points += skill["points"]

    activity_points = 0
    for activity in activities:
        activity_points += activity["points"]

    points_total = skill_points + activity_points
    rank_name = get_rank_from_points(points_total)

    if rank_name == RANK.GOD:
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

    if member and member.roles:
        if check_member_has_role(member, ROLE.PROSPECT):
            return await send_prospect_response(
                interaction, rank_name, rank_icon, member
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
                icon = find_emoji(interaction, "Saradomin")
                alignment_emojis = f"{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}"
            case GOD_ALIGNMENT.ZAMORAK:
                icon = find_emoji(interaction, "Zamorak")
                alignment_emojis = f"{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}"
            case GOD_ALIGNMENT.GUTHIX:
                icon = find_emoji(interaction, "Guthix")
                alignment_emojis = f"{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}{EMPTY_SPACE}{icon}"
            case _:
                icon = find_emoji(interaction, "grass")
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
