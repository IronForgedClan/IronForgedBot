import logging
from typing import Optional

import discord

from ironforgedbot.common.helpers import find_emoji, validate_playername
from ironforgedbot.common.ranks import get_rank_from_member
from ironforgedbot.common.responses import (
    build_ingot_response_embed,
    send_error_response,
)
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLE.ANY)
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
    account_id = str(discord_member.id)[:7] if discord_member is not None else "0123456"

    try:
        member = await STORAGE.read_member(player)
    except StorageError as error:
        return await send_error_response(interaction, str(error))

    if member is None:
        return await send_error_response(
            interaction, f"Member '{player}' could not be found."
        )

    rank_icon = find_emoji(None, str(get_rank_from_member(discord_member)))
    ingot_icon = find_emoji(None, "Ingot")

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
    embed.add_field(name="Account ID", value=account_id)
    embed.add_field(name=f"{ingot_icon} Balance", value=f"{member.ingots:,}")

    await interaction.followup.send(embed=embed)
