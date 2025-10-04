import logging

import discord
from discord.ui import Select, View

from ironforgedbot.commands.raffle.end_raffle import handle_end_raffle
from ironforgedbot.common.logging_utils import log_method_execution

logger = logging.getLogger(__name__)


class EndRaffleView(View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=60)

        self.interaction = interaction

        self.option = Select(
            placeholder="Choose an option...",
            options=[
                discord.SelectOption(
                    label="End Raffle",
                    value="end_raffle",
                    description="Ends the raffle, selects the winner and announces it here.",
                ),
                discord.SelectOption(
                    label="Cancel",
                    value="cancel",
                    description="Do nothing.",
                ),
            ],
        )

        self.option.callback = self.option_callback
        self.add_item(self.option)

    @log_method_execution(logger)
    async def option_callback(self, interaction: discord.Interaction) -> bool:
        value = self.option.values[0]

        if value == "end_raffle":
            await handle_end_raffle(
                await self.interaction.original_response(), interaction
            )

        if value == "cancel":
            await self.interaction.delete_original_response()
            await interaction.response.send_message(
                content="## Cancelled\n🟢 Raffle remains online.",
                ephemeral=True,
            )

        return await super().interaction_check(interaction)
