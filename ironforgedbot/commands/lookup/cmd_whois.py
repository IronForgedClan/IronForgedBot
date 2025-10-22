import logging

import discord
from discord import app_commands

from wom import NameChangeStatus
from ironforgedbot.common.autocompletes import member_nickname_autocomplete
from ironforgedbot.common.helpers import render_relative_time, validate_playername
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.services.wom_service import (
    get_wom_service,
    WomServiceError,
    WomRateLimitError,
    WomTimeoutError,
)

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(player="Player name to get RuneScape name change history for")
@app_commands.autocomplete(player=member_nickname_autocomplete)
async def cmd_whois(interaction: discord.Interaction, player: str):
    """Get player's rsn history

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to get name history.
    """
    assert interaction.guild

    try:
        member, player = validate_playername(
            interaction.guild, player, must_be_member=False
        )
    except Exception as e:
        return await send_error_response(interaction, str(e), report_to_channel=False)

    display_name = member.display_name if member is not None else player

    try:
        async with get_wom_service() as wom_service:
            name_changes = await wom_service.get_player_name_history(player)
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
            interaction, "Error getting name change history", report_to_channel=False
        )

    embed = build_response_embed(
        f"📋 {display_name} | Name History",
        "",
        discord.Colour.purple(),
    )

    if len(name_changes) <= 0:
        embed.add_field(
            name="",
            value="No name changes found for this user.",
            inline=False,
        )
    else:
        field_count = 0
        for change in name_changes:
            if field_count == 24:
                embed.add_field(
                    name="",
                    value=f"...and {text_bold(str(len(name_changes) - field_count))} more not shown.",
                    inline=False,
                )
                break

            if not change.status == NameChangeStatus.Approved:
                continue

            if change.resolved_at is not None:
                timestamp = render_relative_time(change.resolved_at)
            else:
                timestamp = text_bold("pending")

            field_count += 1
            embed.add_field(
                name="",
                value=f"{text_bold(timestamp)}: {change.old_name} → {change.new_name}",
                inline=False,
            )

    await interaction.followup.send(embed=embed)
