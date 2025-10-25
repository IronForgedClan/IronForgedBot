import random
import time
from typing import TYPE_CHECKING, Optional

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    LOW_INGOT_MIN,
)
from ironforgedbot.state import STATE

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


class DoubleOrNothingView(discord.ui.View):
    """Discord UI View for the double-or-nothing button interaction.

    Displays buttons that allow users to risk their winnings for a chance to double them,
    or keep their winnings safely.
    """

    def __init__(self, handler: "TrickOrTreatHandler", user_id: int, amount: int):
        """Initialize the double-or-nothing view.

        Args:
            handler: The TrickOrTreatHandler instance to use for processing the result.
            user_id: The Discord user ID who can interact with this button.
            amount: The amount of ingots at stake.
        """
        super().__init__(timeout=30.0)
        self.handler = handler
        self.user_id = user_id
        self.amount = amount
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        double_button = discord.ui.Button(
            label="🎲 Double",
            style=discord.ButtonStyle.green,
            custom_id="double_or_nothing_double",
            row=0,
        )
        double_button.callback = self._double_callback
        self.add_item(double_button)

        keep_button = discord.ui.Button(
            label="🐔 Keep winnings",
            style=discord.ButtonStyle.secondary,
            custom_id="double_or_nothing_keep",
            row=0,
        )
        keep_button.callback = self._keep_callback
        self.add_item(keep_button)

    async def _double_callback(self, interaction: discord.Interaction):
        """Handle the double-or-nothing button click.

        Args:
            interaction: The Discord interaction from the button click.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your game!", ephemeral=True
            )
            return

        if self.has_interacted:
            await interaction.response.send_message(
                "You already made your choice!", ephemeral=True
            )
            return

        self.has_interacted = True

        await interaction.response.defer()
        if self.message:
            await self.message.delete()

        await process_double_or_nothing(self.handler, interaction, self.amount)

        user_id_str = str(self.user_id)
        if user_id_str in STATE.state["double_or_nothing_offers"]:
            del STATE.state["double_or_nothing_offers"][user_id_str]

        self.stop()

    async def _keep_callback(self, interaction: discord.Interaction):
        """Handle the keep winnings button click.

        Args:
            interaction: The Discord interaction from the button click.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your game!", ephemeral=True
            )
            return

        if self.has_interacted:
            await interaction.response.send_message(
                "You already made your choice!", ephemeral=True
            )
            return

        self.has_interacted = True

        await interaction.response.defer()
        if self.message:
            await self.message.delete()

        user_nickname, ingot_total = await self.handler._get_user_info(
            interaction.user.id
        )

        message = self.handler.double_or_nothing["keep"].format(
            ingot_icon=self.handler.ingot_icon, amount=self.amount
        )
        message += self.handler._get_balance_message(user_nickname, ingot_total)

        embed = self.handler._build_embed(message)
        await interaction.followup.send(embed=embed)

        user_id_str = str(self.user_id)
        if user_id_str in STATE.state["double_or_nothing_offers"]:
            del STATE.state["double_or_nothing_offers"][user_id_str]

        self.stop()

    async def on_timeout(self):
        """Handle the view timing out after 30 seconds."""
        user_id_str = str(self.user_id)
        if user_id_str in STATE.state["double_or_nothing_offers"]:
            del STATE.state["double_or_nothing_offers"][user_id_str]

        if self.has_interacted or not self.message:
            return

        self.clear_items()

        user_nickname, ingot_total = await self.handler._get_user_info(self.user_id)

        message = self.handler.double_or_nothing["expired"].format(
            ingot_icon=self.handler.ingot_icon, amount=self.amount
        )
        if ingot_total is not None:
            message += self.handler._get_balance_message(user_nickname, ingot_total)

        embed = self.handler._build_embed(message)
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass  # Message may have been deleted


async def result_double_or_nothing(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Offer the player a chance to double their winnings or lose them.

    Awards a random amount of ingots between LOW and HIGH ranges, then presents
    a button allowing the player to risk those ingots for a 50/50 chance to double them.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild

    quantity = random.randrange(LOW_INGOT_MIN, HIGH_INGOT_MAX, 1)

    ingot_total = await handler._adjust_ingots(
        interaction,
        quantity,
        interaction.guild.get_member(interaction.user.id),
        reason="Trick or treat: double or nothing initial win",
    )

    if ingot_total is None:
        await interaction.followup.send(
            embed=handler._build_no_ingots_error_response(interaction.user.display_name)
        )
        return

    user_nickname, _ = await handler._get_user_info(interaction.user.id)

    expire_timestamp = int(time.time() + 30)
    expires_formatted = f"<t:{expire_timestamp}:R>"

    offer_message = handler.double_or_nothing["offer"].format(
        ingot_icon=handler.ingot_icon, amount=quantity, expires=expires_formatted
    )
    offer_message += handler._get_balance_message(user_nickname, ingot_total)

    embed = handler._build_embed(offer_message)

    user_id_str = str(interaction.user.id)
    STATE.state["double_or_nothing_offers"][user_id_str] = {
        "amount": quantity,
        "expires_at": time.time() + 30,
    }

    view = DoubleOrNothingView(handler, interaction.user.id, quantity)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message


async def process_double_or_nothing(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction, amount: int
) -> None:
    """Process the result of a double-or-nothing gamble.

    50% chance to win (double the amount) or lose (remove the amount).

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
        amount: The amount of ingots at stake.
    """
    assert interaction.guild

    won = random.random() < 0.5

    user_nickname, _ = await handler._get_user_info(interaction.user.id)

    if won:
        ingot_total = await handler._adjust_ingots(
            interaction,
            amount,
            interaction.guild.get_member(interaction.user.id),
            reason="Trick or treat: double or nothing win",
        )

        if ingot_total is None:
            await interaction.followup.send(
                embed=handler._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = handler.double_or_nothing["win"].format(
            ingot_icon=handler.ingot_icon, total_amount=amount * 2
        )
        message += handler._get_balance_message(user_nickname, ingot_total)
    else:
        ingot_total = await handler._adjust_ingots(
            interaction,
            -amount,
            interaction.guild.get_member(interaction.user.id),
            reason="Trick or treat: double or nothing loss",
        )

        if ingot_total is None:
            await interaction.followup.send(
                embed=handler._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        formatted_amount = f"-{amount:,}"
        message = handler.double_or_nothing["lose"].format(
            ingot_icon=handler.ingot_icon, amount=formatted_amount
        )
        message += handler._get_balance_message(user_nickname, ingot_total)

    embed = handler._build_embed(message)
    await interaction.followup.send(embed=embed)
