import logging
import statistics
from datetime import datetime
from typing import List, Optional

import discord
from discord import app_commands
from tabulate import tabulate

from ironforgedbot.common.activity_check import build_daily_gains
from ironforgedbot.common.autocompletes import member_nickname_autocomplete
from ironforgedbot.common.helpers import (
    find_emoji,
    normalize_discord_string,
    validate_playername,
)
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.ranks import get_rank_from_member
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_code_block
from ironforgedbot.database.database import db
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.services.service_factory import create_member_service
from ironforgedbot.services.wom_service import (
    WomRateLimitError,
    WomServiceError,
    WomTimeoutError,
    get_wom_service,
)

logger = logging.getLogger(__name__)


def _average_daily_gains(daily: List[tuple[datetime, int]]) -> int:
    """Return the mean XP gained per day, including 0-gain days."""
    if not daily:
        return 0
    return sum(xp for _, xp in daily) // len(daily)


def _median_daily_gains(daily: List[tuple[datetime, int]]) -> int:
    """Return the median XP gained per day, including 0-gain days."""
    if not daily:
        return 0
    values = [xp for _, xp in daily]
    return int(statistics.median(values))


def _build_gains_table(daily: List[tuple[datetime, int]]) -> str:
    """Build a formatted markdown table of daily XP gains.

    Args:
        daily: List of (date, xp_gained) tuples ordered oldest to newest.

    Returns:
        A code-block string containing the formatted table.
    """
    rows = [(d.strftime("%Y-%m-%d"), f"{xp:,}") for d, xp in daily]
    table = tabulate(
        rows,
        headers=["Date", "XP Gained"],
        tablefmt="github",
        colalign=("left", "right"),
    )
    return text_code_block(table)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to show gains for (defaults to your nickname)"
)
@app_commands.autocomplete(player=member_nickname_autocomplete)
async def cmd_gains(interaction: discord.Interaction, player: Optional[str] = None):
    """Show a player's daily XP gains over the past 30 days.

    Args:
        interaction: Discord Interaction from CommandTree
        player: Player name to check (defaults to calling user)
    """
    if player is None:
        player = interaction.user.display_name

    if not interaction.guild:
        return

    try:
        member, player = validate_playername(
            interaction.guild, player, must_be_member=False
        )
    except Exception as e:
        return await send_error_response(interaction, str(e), report_to_channel=False)

    if not member:
        return await send_error_response(
            interaction,
            f"Player **{player}** is not a member of this server.",
            report_to_channel=False,
        )

    display_name = member.display_name

    async with db.get_session() as session:
        member_service = create_member_service(session)
        db_member = await member_service.get_member_by_nickname(
            normalize_discord_string(player)
        )

    if not db_member:
        return await send_error_response(
            interaction,
            f"Player **{player}** not found in the database.",
            report_to_channel=False,
        )

    rank_emoji = find_emoji(str(db_member.rank))

    try:
        async with get_wom_service() as wom_service:
            try:
                snapshots = await wom_service.get_player_snapshot_timeline(
                    db_member.nickname
                )
            except WomRateLimitError:
                return await send_error_response(
                    interaction,
                    "WOM API rate limit exceeded. Please try again later.",
                    report_to_channel=False,
                )
            except WomTimeoutError:
                return await send_error_response(
                    interaction,
                    "WOM API connection timed out. Please try again.",
                    report_to_channel=False,
                )
            except WomServiceError:
                return await send_error_response(
                    interaction,
                    "Error retrieving WOM data. Please try again later.",
                    report_to_channel=False,
                )
    except Exception as e:
        logger.error(f"Error fetching WOM snapshot timeline for {player}: {e}")
        return await send_error_response(
            interaction,
            "Unexpected error retrieving gains data.",
            report_to_channel=False,
        )

    daily = build_daily_gains(snapshots)

    if not daily:
        return await send_error_response(
            interaction,
            f"Not enough data available to show daily gains for **{player}**.",
            report_to_channel=False,
        )

    period_start = daily[0][0].strftime("%Y-%m-%d")
    period_end = daily[-1][0].strftime("%Y-%m-%d")
    average_xp = _average_daily_gains(daily)
    median_xp = _median_daily_gains(daily)
    table = _build_gains_table(daily)

    embed = build_response_embed(
        title="📈 Monthly Gains",
        description="Daily XP gained over the **last 30 days**. Use the `check` command to verify you meet the xp requirements of your rank.",
        color=discord.Color.fuchsia(),
    )

    embed.add_field(
        name="Member",
        value=f"{rank_emoji} {normalize_discord_string(display_name)}",
        inline=True,
    )

    embed.add_field(name="Period Start", value=period_start, inline=True)
    embed.add_field(name="Period End", value=period_end, inline=True)

    embed.add_field(name="Average Gains", value=f"{average_xp:,} xp/day", inline=True)
    embed.add_field(name="Median Gains", value=f"{median_xp:,} xp/day", inline=True)
    embed.add_field(name="", value="", inline=True)

    embed.add_field(name="Gains", value=table, inline=False)

    await interaction.followup.send(embed=embed)
