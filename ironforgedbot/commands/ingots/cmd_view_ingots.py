import logging
from typing import Optional

import discord
from discord import app_commands
from tabulate import tabulate

from ironforgedbot.common.helpers import find_emoji, validate_playername
from ironforgedbot.common.ranks import get_rank_from_member
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import (
    build_ingot_response_embed,
    send_error_response,
)
from ironforgedbot.common.text_formatters import text_code_block
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.database.database import db
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.models.changelog import Changelog
from ironforgedbot.services.changelog_service import ChangelogService
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


def format_transaction(changelog: Changelog) -> list[str]:
    """Format a changelog entry into a table row.

    Args:
        changelog: Changelog entry with previous_value, new_value, comment, timestamp, change_type

    Returns:
        List containing [change_string, comment] for table display
    """
    LINE_LIMIT = 38

    previous = int(changelog.previous_value) if changelog.previous_value else 0
    new = int(changelog.new_value) if changelog.new_value else 0
    difference = new - previous

    sign = "+" if difference >= 0 else ""
    change_string = f"{sign}{difference:,}"

    comment = changelog.comment[:LINE_LIMIT] + (
        "..." if len(changelog.comment) > LINE_LIMIT else ""
    )

    return [change_string, comment]


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to view ingots for (defaults to your nickname)"
)
async def cmd_view_ingots(
    interaction: discord.Interaction, player: Optional[str] = None
):
    """View your ingots, or those for another player.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        (optional) player: Runescape username to view ingot count for.
    """
    if player is None:
        player = interaction.user.display_name

    assert interaction.guild

    try:
        discord_member, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    display_name = discord_member.display_name if discord_member is not None else player

    async with db.get_session() as session:
        service = MemberService(session)
        changelog_service = ChangelogService(session)
        member = await service.get_member_by_nickname(player)

        if not member:
            return await send_error_response(
                interaction, f"Member '{player}' could not be found."
            )

        transactions = await changelog_service.latest_ingot_transactions(
            discord_id=member.discord_id, quantity=5
        )

        rank_icon = find_emoji(str(get_rank_from_member(discord_member)))
        ingot_icon = find_emoji("Ingot")

        embed = build_ingot_response_embed(
            title=f"{ingot_icon} Ingot Account",
            description=f"Ingots are our clan currency. Learn how to earn or spend them in <#{CONFIG.INGOT_SHOP_CHANNEL_ID}>.",
        )

        embed.add_field(name="Member", value=f"{rank_icon} {display_name}")
        embed.add_field(name="Balance", value=f"{ingot_icon} {member.ingots:,}")

        if transactions:
            transaction_data = [format_transaction(t) for t in transactions]
            transaction_table = tabulate(
                transaction_data,
                headers=["Change", "Reason"],
                tablefmt="simple",
                colalign=("right", "left"),
            )
            embed.add_field(
                name="Recent Transactions",
                value=text_code_block(transaction_table),
                inline=False,
            )

        await interaction.followup.send(embed=embed)
