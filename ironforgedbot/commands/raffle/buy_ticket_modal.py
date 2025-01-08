import logging

import discord
from discord.ui import Modal, TextInput

from ironforgedbot.common.helpers import find_emoji, normalize_discord_string
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.state import STATE
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


class BuyTicketModal(Modal):
    def __init__(self):
        super().__init__(title="Buy Raffle Tickets")
        self.ticket_embed_color = discord.Colour.from_rgb(115, 136, 217)

        self.ticket_qty = TextInput(
            label="How many tickets?",
            placeholder="10",
            max_length=10,
            required=True,
            style=discord.TextStyle.short,
            custom_id="ticket_qty",
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
                color=self.ticket_embed_color,
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
                f"{text_bold(caller)} not found in storage, please reach out to leadership.",
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
            color=self.ticket_embed_color,
        )

        await interaction.followup.send(embed=embed)
