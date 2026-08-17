import logging

import discord
from discord import app_commands

from ironforgedbot.common.helpers import find_emoji, validate_playername
from ironforgedbot.common.text_formatters import text_ascii_table
from ironforgedbot.commands.hiscore.score_utils import _resolve_rank_display
from ironforgedbot.config import CONFIG
from ironforgedcore.common.normalize import normalize_discord_string
from ironforgedcore.common.ranks import (
    RANK,
    RANK_POINTS,
    get_next_rank_from_points,
    get_rank_from_points,
)
from ironforgedcore.common.time import format_duration_hours
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
    send_member_no_hiscore_values,
    send_not_clan_member,
    send_prospect_response,
)
from ironforgedcore.common.roles import ROLE
from ironforgedbot.common.ranks_discord import get_rank_color_from_points
from ironforgedbot.common.roles_discord import check_member_has_role, has_prospect_role
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.decorators.require_role import require_role
from ironforgedcore.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedcore.http import HTTP, HttpException
from ironforgedcore.models.score import NextPointProgress, ScoreBreakdown
from ironforgedcore.services.score_service import get_score_service

logger = logging.getLogger(__name__)

_TOP_N = 50
_EMBED_TITLE = ":chart_with_upwards_trend: Point Progress"
_EMBED_DESCRIPTION = (
    "The most efficient path to the next **clan point**. Skills, bosses, raids "
    "and clues ranked by the efficient time it takes to complete. "
    f"See <#{CONFIG.RANKINGS_CHANNEL_ID}> for the rank ladder."
)


def _build_summary_embed(
    display_name: str,
    rank_name: str,
    rank_icon: str,
    rank_color: discord.Color,
    god_alignment: str | None,
    points_total: int,
) -> discord.Embed:
    """Build the user-info summary embed"""
    member_icon = find_emoji("Grass") if rank_name == RANK.GOD else rank_icon
    embed = build_response_embed(_EMBED_TITLE, _EMBED_DESCRIPTION, rank_color)

    embed.add_field(
        name="Member",
        value=f"{member_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )

    if rank_name == RANK.GOD:
        alignment_value = (
            f"{rank_icon} {god_alignment}" if god_alignment else "_Unaligned_"
        )
        embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
        embed.add_field(name="God Alignment", value=alignment_value, inline=True)
    else:
        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()]
        next_rank_icon = find_emoji(next_rank_name)
        points_needed = next_rank_point_threshold - points_total

        embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
        embed.add_field(
            name="Next Rank",
            value=f"{next_rank_icon} {next_rank_name} (in {points_needed:,} pts)",
            inline=True,
        )

    return embed


def _row_for_proximity(progress: NextPointProgress) -> tuple[str, str, str]:
    label = (progress.display_name or progress.name).strip()
    remaining = f"{progress.remaining_to_next:,} {progress.unit}"
    suffix = "ehp" if progress.category == "skill" else "ehb"
    ehp_col = format_duration_hours(progress.time_hours, suffix)
    return (label, remaining, ehp_col)


def _build_list_embed(
    proximity: list[NextPointProgress],
    rank_color: discord.Color,
) -> discord.Embed:
    """Build the top-N proximity table embed"""
    if not proximity:
        embed = build_response_embed("", "", rank_color)
        embed.add_field(
            name="No progress yet",
            value=(
                "This player has no qualifying XP or KC yet. "
                "Start grinding to populate the list."
            ),
            inline=False,
        )
        return embed

    rows = [_row_for_proximity(p) for p in proximity]
    table = text_ascii_table(
        rows,
        headers=["Entry", "Next Point In", "Estimate"],
        wrap_widths=[20, None, None],
        colalign=("left", "right", "right"),
    )

    description = (
        table
        + f"\n-# _The EHP/EHB values used in the time calculation are taken directly from the Wise Old Man [ironman efficiency rates](https://wiseoldman.net/ehb/ironman)._"
    )
    return build_response_embed(title="", description=description, color=rank_color)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to check point progress for (defaults to your nickname)"
)
async def cmd_point_progress(
    interaction: discord.Interaction, player: str | None = None
):
    """Show the top 15 skills/activities closest to gaining a point.

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

    points_total = sum(s.points for s in data.skills) + sum(
        a.points for a in (data.clues + data.raids + data.bosses)
    )
    rank_name = get_rank_from_points(points_total)

    if member and member.roles:
        if has_prospect_role(member):
            rank_icon = find_emoji(rank_name)
            return await send_prospect_response(
                interaction, rank_name, rank_icon, member
            )

    if not member or not check_member_has_role(member, ROLE.MEMBER):
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

    rank_icon, rank_color, god_alignment = _resolve_rank_display(
        member, points_total, rank_name
    )
    proximity = await service.get_proximity_to_next_point(data, limit=_TOP_N)

    summary_embed = _build_summary_embed(
        display_name=display_name,
        rank_name=rank_name,
        rank_icon=rank_icon,
        rank_color=rank_color,
        god_alignment=god_alignment,
        points_total=points_total,
    )
    list_embed = _build_list_embed(proximity, rank_color)

    await interaction.followup.send(embeds=[summary_embed, list_embed])
