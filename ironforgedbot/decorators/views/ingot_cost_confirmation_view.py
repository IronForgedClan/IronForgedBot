import logging

import discord
from discord.ui import Button, View

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.database.database import db
from ironforgedbot.services.ingot_service import IngotService

logger = logging.getLogger(__name__)


class IngotCostConfirmationView(View):
    def __init__(
        self,
        cost: int,
        wrapped_function,
        original_args: tuple,
        original_kwargs: dict,
        command_name: str,
    ):
        super().__init__(timeout=60)
        self.cost = cost
        self.wrapped_function = wrapped_function
        self.original_args = original_args
        self.original_kwargs = original_kwargs
        self.command_name = command_name
        self.original_interaction = original_args[0]

        confirm_button = Button(
            label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm"
        )
        confirm_button.callback = self.on_confirm
        self.add_item(confirm_button)

        cancel_button = Button(
            label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel"
        )
        cancel_button.callback = self.on_cancel
        self.add_item(cancel_button)

    async def on_confirm(self, button_interaction: discord.Interaction):
        await button_interaction.response.defer(ephemeral=True)

        async with db.get_session() as session:
            ingot_service = IngotService(session)
            result = await ingot_service.try_remove_ingots(
                button_interaction.user.id,
                -self.cost,
                None,
                f"Command usage: {self.command_name}",
            )

        if not result.status:
            ingot_icon = find_emoji("Ingot")
            embed = build_response_embed(
                title="Insufficient Ingots",
                description=f"You need {ingot_icon} **{self.cost:,}** but only have {ingot_icon} **{result.new_total:,}**",
                color=discord.Colour.red(),
            )
            await self.original_interaction.delete_original_response()
            return await button_interaction.followup.send(embed=embed, ephemeral=True)

        await self.original_interaction.delete_original_response()
        new_args = (button_interaction,) + self.original_args[1:]
        await self.wrapped_function(*new_args, **self.original_kwargs)

    async def on_cancel(self, button_interaction: discord.Interaction):
        await button_interaction.response.defer(ephemeral=True)
        await self.original_interaction.delete_original_response()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
