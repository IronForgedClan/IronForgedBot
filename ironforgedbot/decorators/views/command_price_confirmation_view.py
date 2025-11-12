import logging

import discord
from discord.ui import Button, View

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.database.database import db
from ironforgedbot.services.ingot_service import IngotService

logger = logging.getLogger(__name__)


class CommandPriceConfirmationView(View):
    def __init__(
        self,
        cost: int,
        wrapped_function,
        original_args: tuple,
        original_kwargs: dict,
        command_name: str,
        user_id: int,
    ):
        super().__init__(timeout=30)
        self.cost = cost
        self.wrapped_function = wrapped_function
        self.original_args = original_args
        self.original_kwargs = original_kwargs
        self.command_name = command_name
        self.original_interaction = original_args[0]
        self.user_id = user_id
        self.confirmation_message = None

        confirm_button = Button(
            label="Pay", style=discord.ButtonStyle.green, custom_id="confirm"
        )
        confirm_button.callback = self.on_confirm
        self.add_item(confirm_button)

        cancel_button = Button(
            label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel"
        )
        cancel_button.callback = self.on_cancel
        self.add_item(cancel_button)

    async def on_confirm(self, button_interaction: discord.Interaction):
        if button_interaction.user.id != self.user_id:
            await button_interaction.response.send_message(
                "This confirmation is not for you.", ephemeral=True
            )
            return

        self.stop()

        async with db.get_session() as session:
            ingot_service = IngotService(session)
            result = await ingot_service.try_remove_ingots(
                button_interaction.user.id,
                -self.cost,
                None,
                f"Command usage: {self.command_name}",
            )

        self.clear_items()

        ingot_icon = find_emoji("Ingot")

        if not result.status:
            await button_interaction.response.defer(ephemeral=True)
            you_have_string = (
                f"And you only have {ingot_icon} **{result.new_total:,}**."
                if result.new_total > 0
                else "You're skint mate 🤷‍♂️"
            )
            error_embed = build_response_embed(
                title="❌ Insufficient Funds",
                description=f"This command costs {ingot_icon} **{self.cost:,}**.\n\n{you_have_string}",
                color=discord.Colour.red(),
            )
            await self.confirmation_message.edit(embed=error_embed, view=self)
            return

        await button_interaction.response.defer(ephemeral=True)
        await self.confirmation_message.delete()

        await self.wrapped_function(*self.original_args, **self.original_kwargs)

    async def on_cancel(self, button_interaction: discord.Interaction):
        if button_interaction.user.id != self.user_id:
            await button_interaction.response.send_message(
                "This confirmation is not for you.", ephemeral=True
            )
            return

        self.stop()
        await button_interaction.response.defer(ephemeral=True)

        await self.confirmation_message.delete()
        await self.original_interaction.delete_original_response()

    async def on_timeout(self):
        await self.confirmation_message.delete()
        await self.original_interaction.delete_original_response()
