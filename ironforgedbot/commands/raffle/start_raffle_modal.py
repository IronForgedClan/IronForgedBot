import logging

import discord
from discord.ui import Modal, TextInput

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


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
        await interaction.response.defer(thinking=True, ephemeral=True)
        price = 0

        try:
            price = int(self.ticket_price.value)
        except ValueError:
            return await send_error_response(
                interaction,
                f"{text_bold(self.ticket_price.value)} is an invalid ticket price.",
            )

        if price < 1:
            return await send_error_response(
                interaction,
                f"{text_bold(self.ticket_price.value)} is an invalid ticket price.",
            )

        STATE.state["raffle_on"] = True
        STATE.state["raffle_price"] = price

        ticket_icon = find_emoji(None, "Raffle_Ticket")
        ingot_icon = find_emoji(None, "Ingot")

        await interaction.followup.send(
            f"## {ticket_icon} Raffle Started\nTicket Price: {ingot_icon} **{int(price):,}**\n\n"
            "- Members can now buy raffle tickets with the `/raffle` command.\n"
            "- Admins can now end the raffle and select a winner by running the "
            "`/raffle` command and clicking the red 'End Raffle' button.",
        )
