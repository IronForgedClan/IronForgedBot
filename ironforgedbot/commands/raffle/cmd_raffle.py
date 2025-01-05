import logging

import discord

from ironforgedbot.commands.raffle.raffle_menu_view import RaffleMenuView
from ironforgedbot.common.helpers import (
    find_emoji,
)
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.decorators import require_role
from ironforgedbot.state import STATE
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER, ephemeral=True)
async def cmd_raffle(interaction: discord.Interaction):
    """Play or control the raffle"""
    assert interaction.guild

    embed = await build_embed(interaction)
    if not embed:
        return

    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        return await send_error_response(interaction, "Unable to get member details.")

    menu = RaffleMenuView(
        check_member_has_role(member, ROLE.LEADERSHIP, or_higher=True)
    )
    menu.message = await interaction.followup.send(embed=embed, view=menu)


async def build_embed(interaction: discord.Interaction) -> discord.Embed | None:
    ticket_icon = find_emoji(None, "Raffle_Ticket")
    ingot_icon = find_emoji(None, "Ingot")
    ticket_price = STATE.state["raffle_price"]
    embed_color = (
        discord.Colour.green() if STATE.state["raffle_on"] else discord.Colour.red()
    )

    try:
        all_tickets = await STORAGE.read_raffle_tickets()
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error ending raffle: {error}"
        )
        return None

    my_ticket_count = 0
    total_tickets = 0
    prize_pool = 0

    for id, qty in all_tickets.items():
        if id == interaction.user.id:
            my_ticket_count = qty

        total_tickets += qty

    prize_pool = int(total_tickets * (STATE.state["raffle_price"] / 2))

    embed = build_response_embed(
        title=f"{ticket_icon} Iron Forged Raffle",
        description="",
        color=embed_color,
    )
    embed.add_field(
        name="Raffle Status",
        value="🟢 ONLINE" if STATE.state["raffle_on"] else "🔴 OFFLINE",
        inline=False,
    )
    if STATE.state["raffle_on"]:
        embed.add_field(
            name="Ticket Price",
            value=f"{ingot_icon} {ticket_price:,}",
            inline=True,
        )
        embed.add_field(
            name="My Tickets", value=f"{ticket_icon} {my_ticket_count:,}", inline=True
        )
        embed.add_field(
            name="Prize Pool", value=f"{ingot_icon} {prize_pool:,}", inline=True
        )

    embed.set_thumbnail(
        url="https://oldschool.runescape.wiki/images/thumb/Mounted_coins_built.png/250px-Mounted_coins_built.png"
    )

    return embed
