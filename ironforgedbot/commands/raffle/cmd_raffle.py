import logging
import random
from typing import Optional

import discord
from discord.ui import Button, Modal, TextInput, View

from ironforgedbot.commands.raffle.build_winner_image import build_winner_image_file
from ironforgedbot.commands.raffle.start_raffle_modal import StartRaffleModal
from ironforgedbot.common.helpers import (
    find_emoji,
    find_member_by_nickname,
    normalize_discord_string,
)
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold, text_sub
from ironforgedbot.decorators import require_role
from ironforgedbot.state import STATE
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER, ephemeral=True)
async def cmd_raffle(interaction: discord.Interaction):
    """Play or control the raffle"""
    # file = await build_winner_image_file("oxore", 5105000)
    # return await interaction.followup.send(file=file)

    embed = await build_embed(interaction)
    if not embed:
        return

    menu = build_menu(interaction)
    menu.message = await interaction.followup.send(embed=embed, view=menu)


async def build_embed(interaction: discord.Interaction):
    ticket_icon = find_emoji(None, "Raffle_Ticket")
    ingot_icon = find_emoji(None, "Ingot")
    ticket_price = STATE.state["raffle_price"]
    embed_color = (
        discord.Colour.green() if STATE.state["raffle_on"] else discord.Colour.red()
    )

    try:
        all_tickets = await STORAGE.read_raffle_tickets()
    except StorageError as error:
        return await send_error_response(
            interaction, f"Encountered error ending raffle: {error}"
        )

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
            self.message = await self.message.edit(view=None)

        return await super().on_timeout()

    async def handle_buy_tickets(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BuyTicketModal())

        if self.message:
            self.message = await self.message.delete()

    async def handle_start_raffle(self, interaction: discord.Interaction):
        await interaction.response.send_modal(StartRaffleModal())

        if self.message:
            self.message = await self.message.delete()

    async def handle_end_raffle(self, interaction: discord.Interaction):
        await interaction.response.defer()

        async def handle_end_raffle_error(message):
            if self.message:
                self.message = await self.message.delete()

            return await send_error_response(interaction, message)

        assert interaction.guild

        if self.message:
            self.message = await self.message.edit(
                content="## Ending raffle\nSelecting winner, standby...",
                embed=None,
                view=None,
            )

        try:
            current_tickets = await STORAGE.read_raffle_tickets()
        except StorageError as error:
            return await handle_end_raffle_error(
                f"Encountered error ending raffle: {error}"
            )

        if len(current_tickets) < 1:
            return await handle_end_raffle_error(
                "Raffle ended without any tickets sold."
            )

        try:
            members = await STORAGE.read_members()
        except StorageError as error:
            return await handle_end_raffle_error(
                f"Encountered error reading current members: {error}"
            )

        # Calculate valid entries
        current_members = {}
        for member in members:
            current_members[member.id] = member.runescape_name

        entries = []
        for id, ticket_count in current_tickets.items():
            # Ignore members who have left the clan since buying tickets
            if current_members.get(id) is not None:
                entries.extend([current_members.get(id)] * ticket_count)

        if len(entries) < 1:
            return await handle_end_raffle_error(
                "Raffle ended without any valid entries. "
                "May require manual data purge.",
            )

        # Calculate winner
        random.shuffle(entries)
        winner = random.choice(entries)
        winning_discord_member = find_member_by_nickname(interaction.guild, winner)
        winnings = int(len(entries) * (STATE.state["raffle_price"] / 2))

        logger.info(entries)
        logger.info(winner)

        # Award winnings
        try:
            member = await STORAGE.read_member(
                normalize_discord_string(winning_discord_member.display_name)
            )
        except StorageError as error:
            return await handle_end_raffle_error(str(error))

        if member is None:
            return await handle_end_raffle_error(
                f"Winning member '{winning_discord_member.display_name}' not found in storage.",
            )

        member.ingots += winnings

        try:
            await STORAGE.update_members(
                [member],
                interaction.user.display_name,
                note=f"[BOT] Raffle winnings ({winnings:,})",
            )
        except StorageError as error:
            return await handle_end_raffle_error(error)

        # Announce winner
        ticket_icon = find_emoji(None, "Raffle_Ticket")
        ingot_icon = find_emoji(None, "Ingot")
        file = await build_winner_image_file(winner, int(winnings))

        winner_ticket_count = current_tickets[winning_discord_member.id]
        winner_spent = winner_ticket_count * STATE.state["raffle_price"]
        winner_profit = winnings - winner_spent
        await interaction.followup.send(
            (
                f"## {ticket_icon} Congratulations {winning_discord_member.mention}!!\n"
                f"You have won {ingot_icon} {text_bold(f"{winnings:,}")} ingots!\n\n"
                f"You spent {ingot_icon} {text_bold(f"{winner_spent:,}")} on {ticket_icon} "
                f"{text_bold(f"{winner_ticket_count:,}")} tickets.\n"
                f"Resulting in {ingot_icon} {text_bold(f"{winner_profit:,}")} profit.\n"
                + (f"{text_sub('ouch')}\n\n" if winner_profit < 0 else "\n")
                + f"There were a total of {ticket_icon} {text_bold(f"{len(entries):,}")} entries.\n"
                "Thank you everyone for participating!"
            ),
            file=file,
        )

        # Cleanup
        try:
            await STORAGE.delete_raffle_tickets(
                normalize_discord_string(interaction.user.display_name).lower()
            )
        except StorageError as error:
            return await handle_end_raffle_error(
                f"Encountered error clearing ticket storage: {error}"
            )

        if self.message:
            self.message = await self.message.delete()

        STATE.state["raffle_on"] = False
        STATE.state["raffle_price"] = 0


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
        await interaction.response.defer(thinking=True)
        caller = normalize_discord_string(interaction.user.display_name)

        try:
            qty = int(self.ticket_qty.value)
        except ValueError:
            return await send_error_response(
                interaction,
                f"{text_bold(caller)} tried to buy an invalid quantity of tickets.",
            )

        ticket_icon = find_emoji(None, "Raffle_Ticket")
        ingot_icon = find_emoji(None, "Ingot")

        if qty < 1:
            embed = build_response_embed(
                title=f"{ticket_icon} Ticket Purchase",
                description=(
                    f"{text_bold(caller)} just tried to buy {ticket_icon} {text_bold(f"{qty:,}")} raffle "
                    f"tickets. What a joker."
                ),
                color=discord.Colour.gold(),
            )

            return await interaction.followup.send(embed=embed)

        try:
            member = await STORAGE.read_member(caller)
        except StorageError as error:
            logger.error(error)
            return await send_error_response(
                interaction,
                f"Encountered error reading member {text_bold(caller)} from storage.",
            )

        if member is None:
            return await send_error_response(
                interaction,
                f"{caller} not found in storage, please reach out to leadership.",
            )

        cost = qty * STATE.state["raffle_price"]
        if cost > member.ingots:
            return await send_error_response(
                interaction,
                f"{text_bold(caller)} does not have enough ingots for {ticket_icon} {text_bold(f"{qty:,}")} "
                f"tickets.\n\nCost: {ingot_icon} {text_bold(f"{cost:,}")}\nBalance: "
                f"{ingot_icon} {text_bold(f"{member.ingots:,}")}\n\n"
                f"You can afford a maximum of {ticket_icon} "
                f"{text_bold(f"{round(member.ingots/STATE.state['raffle_price']):,}")} tickets.",
            )

        logger.info(f"Buying {qty:,} tickets for {caller}")
        member.ingots -= cost
        try:
            await STORAGE.update_members(
                [member], caller, note=f"Pay for {qty} raffle tickets"
            )
        except StorageError as error:
            logger.error(error)
            return await send_error_response(
                interaction,
                f"Encountered error updating ingot count for {text_bold(caller)}.",
            )

        try:
            await STORAGE.add_raffle_tickets(member.id, qty)
        except StorageError as error:
            logger.error(error)
            return await send_error_response(
                interaction,
                f"Encountered error saving raffle tickets for {text_bold(caller)}.\n"
                "Ingots have been deducted, please contact a member of staff.",
            )

        embed = build_response_embed(
            title=f"{ticket_icon} Ticket Purchase",
            description=(
                f"{text_bold(caller)} just bought {ticket_icon} {text_bold(f"{qty:,}")} raffle "
                f"ticket{'s' if qty > 1 else ''} for {ingot_icon} {text_bold(f"{cost:,}")}."
            ),
            color=discord.Colour.gold(),
        )

        await interaction.followup.send(embed=embed)
