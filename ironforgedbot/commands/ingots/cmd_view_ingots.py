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
from ironforgedbot.database.database import db
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.services.changelog_service import ChangelogService
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


def format_transaction(changelog: Changelog) -> list:
    """Format a changelog entry into a table row.

    Args:
        changelog: Changelog entry with previous_value, new_value, comment, timestamp, change_type

    Returns:
        List containing [change_string, comment] for table display
    """
    previous = int(changelog.previous_value) if changelog.previous_value else 0
    new = int(changelog.new_value) if changelog.new_value else 0
    difference = new - previous

    sign = "+" if difference >= 0 else ""
    change_string = f"{sign}{difference:,}"

    return [change_string, changelog.comment]


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

        embed_thumbnail = ""
        if member.ingots > 0:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Coins_4_detail.png/120px-Coins_4_detail.png"
        if member.ingots >= 100_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Coins_5_detail.png/120px-Coins_5_detail.png"
        if member.ingots >= 350_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Coins_25_detail.png/120px-Coins_25_detail.png"
        if member.ingots >= 750_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Coins_100_detail.png/120px-Coins_100_detail.png"
        if member.ingots >= 2_500_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Coins_250_detail.png/120px-Coins_250_detail.png"
        if member.ingots >= 5_000_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Coins_1000_detail.png/120px-Coins_1000_detail.png"
        if member.ingots >= 10_000_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Platinum_token_3_detail.png/120px-Platinum_token_3_detail.png"
        if member.ingots >= 15_000_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Platinum_token_4_detail.png/120px-Platinum_token_4_detail.png"
        if member.ingots >= 20_000_000:
            embed_thumbnail = "https://oldschool.runescape.wiki/images/thumb/Platinum_token_detail.png/120px-Platinum_token_detail.png"

        embed = build_ingot_response_embed(
            title=f"{rank_icon} {display_name} | Ingots",
            description="",
        )

        embed.set_thumbnail(url=embed_thumbnail)
        embed.add_field(name="Account ID", value=member.id[-10:])
        embed.add_field(name="Balance", value=f"{ingot_icon} {member.ingots:,}")

        if transactions:
            transaction_data = [format_transaction(t) for t in transactions]
            transaction_table = tabulate(
                transaction_data,
                headers=["Change", "Reason"],
                tablefmt="github",
                colalign=("right", "left"),
            )
            embed.add_field(
                name="Recent Transactions",
                value=text_code_block(transaction_table),
                inline=False,
            )

        await interaction.followup.send(embed=embed)
