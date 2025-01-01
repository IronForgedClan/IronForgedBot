import logging
import random
from typing import Optional
import discord
from discord.ui import Button, Modal, TextInput, View
from ironforgedbot.common.helpers import (
    find_emoji,
    find_member_by_nickname,
    normalize_discord_string,
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
    embed = build_embed()
    menu = build_menu(interaction)

    menu.message = await interaction.followup.send(embed=embed, view=menu)


def build_embed():
    ingot_icon = find_emoji(None, "Ingot")
    ticket_price = STATE.state["raffle_price"]
    embed_color = (
        discord.Colour.green() if STATE.state["raffle_on"] else discord.Colour.red()
    )

    embed = build_response_embed(
        title=f"{ingot_icon} Iron Forged Raffle 💰",
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
        embed.add_field(name="My Tickets", value="🎫 3,000", inline=True)
        embed.add_field(name="Prize Pool", value=f"{ingot_icon} 30,250", inline=True)

    embed.set_thumbnail(
        url="https://oldschool.runescape.wiki/images/thumb/Mounted_coins_built.png/250px-Mounted_coins_built.png"
    )

    return embed


def build_menu(interaction: discord.Interaction):
    assert interaction.guild
    member = interaction.guild.get_member(interaction.user.id)
    assert member
    is_admin = check_member_has_role(member, ROLE.LEADERSHIP, or_higher=True)

    return RaffleMenuView(is_admin)


class RaffleMenuView(View):
    def __init__(self, is_admin=False):
        super().__init__(timeout=60)
        self.message: Optional[discord.Message] = None

        self.add_item(
            Button(
                label="Buy Tickets",
                style=discord.ButtonStyle.primary,
                emoji="🎫",
                disabled=False if STATE.state["raffle_on"] else True,
                custom_id="buy_tickets",
                row=0,
            )
        )

        if is_admin:
            self.add_item(
                Button(
                    label="End Raffle",
                    style=discord.ButtonStyle.red,
                    custom_id="end_raffle",
                    disabled=False if STATE.state["raffle_on"] else True,
                    row=1,
                )
            )

            self.add_item(
                Button(
                    label="Start Raffle",
                    style=discord.ButtonStyle.green,
                    custom_id="start_raffle",
                    disabled=True if STATE.state["raffle_on"] else False,
                    row=1,
                )
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data is not None:
            custom_id = interaction.data.get("custom_id", None)

            if custom_id == "buy_tickets":
                await self.handle_buy_tickets(interaction)
            if custom_id == "start_raffle":
                await self.handle_start_raffle(interaction)
            if custom_id == "end_raffle":
                await self.handle_end_raffle(interaction)

        return await super().interaction_check(interaction)

    async def on_timeout(self) -> None:
        if self.message:
            # await self.message.delete()
            await self.message.edit(view=None)

        return await super().on_timeout()

    async def handle_buy_tickets(self, interaction: discord.Interaction):
        modal = BuyTicketModal()
        await interaction.response.send_modal(modal)

    async def handle_start_raffle(self, interaction: discord.Interaction):
        if not self.message:
            return

        await interaction.response.send_modal(StartRaffleModal())
        await self.message.edit(embed=build_embed(), view=build_menu(interaction))

    async def handle_end_raffle(self, interaction: discord.Interaction):
        assert interaction.guild
        STATE.state["raffle_on"] = False

        try:
            current_tickets = await STORAGE.read_raffle_tickets()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error ending raffle: {error}"
            )
            return

        try:
            members = await STORAGE.read_members()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading current members: {error}"
            )
            return

        await interaction.response.edit_message(
            embed=build_embed(), view=build_menu(interaction)
        )

        id_rsn = {}
        for member in members:
            id_rsn[member.id] = member.runescape_name

        entries = []
        for id, ticket_count in current_tickets.items():
            # Account for users who left clan since buying tickets.
            if id_rsn.get(id) is not None:
                entries.extend([id_rsn.get(id)] * ticket_count)

        winner = entries[random.randrange(0, len(entries))]
        winning_member = find_member_by_nickname(interaction.guild, winner)

        winnings = len(entries) * (STATE.state["raffle_price"] / 2)

        # TODO: Make this more fun by adding an entries file or rendering a graphic
        await interaction.followup.send(
            f"{winning_member.mentioned_in} has won {winnings:,} ingots out of {len(entries)} entries!"
        )

        try:
            await STORAGE.delete_raffle_tickets(
                normalize_discord_string(interaction.user.display_name).lower()
            )
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error clearing ticket storage: {error}"
            )
            return


class StartRaffleModal(Modal):
    def __init__(self):
        super().__init__(title="Start Raffle")

        self.ticket_price = TextInput(
            label="Price per ticket",
            placeholder="5000",
            required=True,
            style=discord.TextStyle.short,
        )

        self.add_item(self.ticket_price)

    async def on_submit(self, interaction: discord.Interaction):
        price = self.ticket_price.value

        if not price.isdigit():
            await interaction.response.send_message("Invalid input.", ephemeral=True)

        STATE.state["raffle_on"] = True
        STATE.state["raffle_price"] = int(price)

        await interaction.response.send_message(
            f"## Starting Raffle\nTicket Price: {int(price):,}", ephemeral=True
        )


class BuyTicketModal(Modal):
    def __init__(self):
        super().__init__(title="Buy Raffle Tickets")

        self.ticket_qty = TextInput(
            label="How many tickets?",
            placeholder="10",
            max_length=10,
            required=True,
            style=discord.TextStyle.short,
        )

        self.add_item(self.ticket_qty)

    async def on_submit(self, interaction: discord.Interaction):
        qty = self.ticket_qty.value
        caller = normalize_discord_string(interaction.user.display_name)

        if not qty.isdigit():
            return await interaction.response.send_message(
                "Invalid input.", ephemeral=True
            )

        qty = int(qty)
        if qty < 1:
            return await interaction.response.send_message(
                "Invalid input.", ephemeral=True
            )

        try:
            member = await STORAGE.read_member(caller)
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading member from storage: {error}"
            )
            return

        if member is None:
            await send_error_response(
                interaction,
                f"{caller} not found in storage, please reach out to leadership.",
            )
            return

        cost = qty * STATE.state["raffle_price"]
        if cost > member.ingots:
            await interaction.followup.send(
                f"{caller} does not have enough ingots for {qty} tickets.\n"
                + f"Cost: {cost}, current ingots: {member.ingots}"
            )
            return

        member.ingots -= cost
        try:
            await STORAGE.update_members([member], caller, note="Bought raffle tickets")
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error updating member ingot count: {error}"
            )
            return

        try:
            await STORAGE.add_raffle_tickets(member.id, qty)
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error adding raffle tickets: {error}"
            )

            return

        await interaction.followup.send(
            f"{caller} successfully bought {qty} tickets for {cost} ingots!"
        )

        await interaction.response.send_message(f"You entered: {qty}", ephemeral=True)
