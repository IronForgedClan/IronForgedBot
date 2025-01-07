import logging
from typing import Optional

import discord
from discord.ui import Button, View

from ironforgedbot.commands.raffle.buy_ticket_modal import BuyTicketModal
from ironforgedbot.commands.raffle.end_raffle import handle_end_raffle
from ironforgedbot.commands.raffle.start_raffle_modal import StartRaffleModal
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


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
                await handle_end_raffle(self.message, interaction)
                self.message = None

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
