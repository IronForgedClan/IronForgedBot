"""Double-or-nothing outcome for trick-or-treat."""

import random
import time
from typing import TYPE_CHECKING, Optional

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    LOW_INGOT_MIN,
)
from ironforgedbot.state import STATE

if TYPE_CHECKING:
    from ironforgedbot.commands.holiday.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


class DoubleOrNothingView(discord.ui.View):
    """Discord UI View for the double-or-nothing button interaction.

    Displays buttons that allow users to risk their winnings for a chance to double them,
    or keep their winnings safely.
    The view times out after 30 seconds.
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
            label="🐔 Nothing",
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

        # Delete the original message
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

        # Delete the original message
        await interaction.response.defer()
        if self.message:
            await self.message.delete()

        # Get member nickname from database
        from ironforgedbot.database.database import db
        from ironforgedbot.services.member_service import MemberService

        async with db.get_session() as session:
            member_service = MemberService(session)
            user_member = await member_service.get_member_by_discord_id(
                interaction.user.id
            )
            user_nickname = user_member.nickname if user_member else "User"
            ingot_total = user_member.ingots if user_member else 0

        # Send keep winnings message
        message = self.handler.DOUBLE_OR_NOTHING_KEEP.format(
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

        # Remove all buttons
        self.clear_items()

        # Get current ingot total and nickname from database
        from ironforgedbot.database.database import db
        from ironforgedbot.services.member_service import MemberService

        ingot_total = None
        user_nickname = "User"

        async with db.get_session() as session:
            member_service = MemberService(session)
            user_member = await member_service.get_member_by_discord_id(self.user_id)
            if user_member:
                ingot_total = user_member.ingots
                user_nickname = user_member.nickname

        # Update the message with timeout notification
        message = self.handler.DOUBLE_OR_NOTHING_EXPIRED.format(
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

    # Award the ingots
    ingot_total = await handler._adjust_ingots(
        interaction,
        quantity,
        interaction.guild.get_member(interaction.user.id),
    )

    if ingot_total is None:
        await interaction.followup.send(
            embed=handler._build_no_ingots_error_response(interaction.user.display_name)
        )
        return

    # Get member nickname from database
    from ironforgedbot.database.database import db
    from ironforgedbot.services.member_service import MemberService

    async with db.get_session() as session:
        member_service = MemberService(session)
        user_member = await member_service.get_member_by_discord_id(interaction.user.id)
        user_nickname = user_member.nickname if user_member else "User"

    # Calculate expiration timestamp and format as Discord countdown
    expire_timestamp = int(time.time() + 30)
    expires_formatted = f"<t:{expire_timestamp}:R>"

    # Create the offer message
    offer_message = handler.DOUBLE_OR_NOTHING_OFFER.format(
        ingot_icon=handler.ingot_icon, amount=quantity, expires=expires_formatted
    )
    offer_message += handler._get_balance_message(user_nickname, ingot_total)

    embed = handler._build_embed(offer_message)

    # Store the offer in state
    user_id_str = str(interaction.user.id)
    STATE.state["double_or_nothing_offers"][user_id_str] = {
        "amount": quantity,
        "expires_at": time.time() + 30,
    }

    # Create and send the view with the button
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

    # 50/50 chance
    won = random.random() < 0.5

    # Get member nickname from database
    from ironforgedbot.database.database import db
    from ironforgedbot.services.member_service import MemberService

    async with db.get_session() as session:
        member_service = MemberService(session)
        user_member = await member_service.get_member_by_discord_id(interaction.user.id)
        user_nickname = user_member.nickname if user_member else "User"

    if won:
        # Award additional ingots (they already have the original amount)
        ingot_total = await handler._adjust_ingots(
            interaction,
            amount,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total is None:
            await interaction.followup.send(
                embed=handler._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = handler.DOUBLE_OR_NOTHING_WIN.format(
            ingot_icon=handler.ingot_icon, total_amount=amount * 2
        )
        message += handler._get_balance_message(user_nickname, ingot_total)
    else:
        # Remove the ingots they won
        ingot_total = await handler._adjust_ingots(
            interaction,
            -amount,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total is None:
            await interaction.followup.send(
                embed=handler._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = handler.DOUBLE_OR_NOTHING_LOSE.format(
            ingot_icon=handler.ingot_icon, amount=amount
        )
        message += handler._get_balance_message(user_nickname, ingot_total)

    embed = handler._build_embed(message)
    await interaction.followup.send(embed=embed)
