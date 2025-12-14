import logging
from typing import Optional

import discord
from discord import app_commands

from ironforgedbot.common.activity_check import check_member_activity
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
from ironforgedbot.database.database import db
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.services.service_factory import (
    create_absent_service,
    create_member_service,
)
from ironforgedbot.services.wom_service import (
    get_wom_service,
    WomServiceError,
    WomRateLimitError,
    WomTimeoutError,
)

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to check activity for (defaults to your nickname)"
)
@app_commands.autocomplete(player=member_nickname_autocomplete)
async def cmd_check(interaction: discord.Interaction, player: Optional[str] = None):
    """Check if a player meets monthly activity requirements.

    Args:
        interaction: Discord Interaction from CommandTree
        player: Player name to check (defaults to calling user)
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

        absent_service = create_absent_service(session)
        absentee_list = await absent_service.process_absent_members()
        known_absentees = [absentee.nickname.lower() for absentee in absentee_list]

    try:
        async with get_wom_service() as wom_service:
            try:
                player_gains = await wom_service.get_player_monthly_gains(
                    db_member.nickname
                )

                wom_group = await wom_service.get_group_membership_data()

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
        logger.error(f"Error fetching WOM data for {player}: {e}")
        return await send_error_response(
            interaction,
            "Unexpected error retrieving activity data.",
            report_to_channel=False,
        )

    try:
        result = check_member_activity(
            wom_username=db_member.nickname,
            wom_group=wom_group,
            monthly_gains=player_gains,
            absentees=known_absentees,
        )
    except Exception as e:
        logger.error(f"Error checking activity for {player}: {e}")
        return await send_error_response(
            interaction,
            "Error processing activity check.",
            report_to_channel=False,
        )

    if result.skip_reason == "not_in_group":
        return await send_error_response(
            interaction,
            f"Player **{player}** not found in the clan.",
            report_to_channel=False,
        )

    if result.is_prospect:
        prospect_emoji = find_emoji("Prospect")
        status_text = "✅ Safe"
        embed_color = discord.Colour.green()
        note_text = f"This member is a {prospect_emoji} **Prospect** and immune from activity purges for the duration of their probation."
    elif result.is_exempt:
        status_text = "✅ Safe"
        embed_color = discord.Colour.green()
        note_text = "This member has a role that exempts them from activity checks."
    elif result.is_active:
        status_text = "✅ Safe"
        embed_color = discord.Colour.green()
        note_text = ""
    else:
        status_text = "❌ In danger"
        embed_color = discord.Colour.red()
        note_text = ""

    if result.is_absent:
        note_text += f"Member is marked as absent."

    embed = build_response_embed(
        title=f"📊 Activity Check",
        description="Inactive members may be removed from the clan to make space for active members. For more information see <#123>.",
        color=embed_color,
    )

    embed.set_thumbnail(
        url="https://oldschool.runescape.wiki/images/Count_Check_chathead.png"
    )

    embed.add_field(name="Member", value=f"{rank_emoji} {display_name}", inline=True)

    embed.add_field(
        name="Status",
        value=status_text,
        inline=True,
    )

    embed.add_field(name="", value="", inline=True)

    embed.add_field(
        name="Requirement",
        value=f"{result.xp_threshold:,} xp/month",
        inline=True,
    )

    embed.add_field(
        name="Gained",
        value=f"{result.xp_gained:,} xp",
        inline=True,
    )

    embed.add_field(name="", value="", inline=True)

    if note_text:
        embed.add_field(name="Note", value=note_text, inline=False)

    await interaction.followup.send(embed=embed)
