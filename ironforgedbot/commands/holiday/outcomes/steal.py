"""Steal outcome for trick-or-treat."""

import logging
import random
from typing import TYPE_CHECKING, List, Optional

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    LOW_INGOT_MIN,
)
from ironforgedbot.common.roles import ROLE
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService

if TYPE_CHECKING:
    from ironforgedbot.commands.holiday.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )

logger = logging.getLogger(__name__)


class StealTargetView(discord.ui.View):
    """Discord UI View for the steal target selection.

    Displays buttons for each Leadership member that can be stolen from,
    plus a "Walk Away" button to abort safely.
    The view times out after 30 seconds.
    """

    def __init__(
        self,
        handler: "TrickOrTreatHandler",
        user_id: int,
        amount: int,
        targets: List[discord.Member],
    ):
        """Initialize the steal target view.

        Args:
            handler: The TrickOrTreatHandler instance to use for processing the result.
            user_id: The Discord user ID who can interact with this view.
            amount: The amount of ingots at stake.
            targets: List of Leadership members to display as targets (max 3).
        """
        super().__init__(timeout=30.0)
        self.handler = handler
        self.user_id = user_id
        self.amount = amount
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        for target in targets:
            button = discord.ui.Button(
                label=target.display_name,
                style=discord.ButtonStyle.danger,
                custom_id=f"steal_{target.id}",
            )
            button.callback = self._create_steal_callback(target)
            self.add_item(button)

        walk_away_button = discord.ui.Button(
            label="🚶 Walk Away",
            style=discord.ButtonStyle.secondary,
            custom_id="steal_walk_away",
        )
        walk_away_button.callback = self._walk_away_callback
        self.add_item(walk_away_button)

    def _create_steal_callback(self, target: discord.Member):
        """Create a callback function for a specific target button.

        Args:
            target: The target member this button represents.

        Returns:
            An async callback function for the button.
        """

        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This isn't your heist!", ephemeral=True
                )
                return

            if self.has_interacted:
                await interaction.response.send_message(
                    "You already made your choice!", ephemeral=True
                )
                return

            self.has_interacted = True

            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await interaction.response.edit_message(view=self)

            await process_steal(self.handler, interaction, self.amount, target)

            self.stop()

        return callback

    async def _walk_away_callback(self, interaction: discord.Interaction):
        """Handle the walk away button click.

        Args:
            interaction: The Discord interaction from the button click.
        """
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your heist!", ephemeral=True
            )
            return

        if self.has_interacted:
            await interaction.response.send_message(
                "You already made your choice!", ephemeral=True
            )
            return

        self.has_interacted = True

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

        embed = self.handler._build_embed(self.handler.STEAL_WALK_AWAY)
        await interaction.followup.send(embed=embed)

        self.stop()

    async def on_timeout(self):
        """Handle the view timing out after 30 seconds."""
        if self.has_interacted or not self.message:
            return

        # Disable all buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        # Update the message with timeout notification
        embed = self.handler._build_embed(self.handler.STEAL_EXPIRED)
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass  # Message may have been deleted


async def result_steal(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Offer the player a chance to steal ingots from Leadership members.

    Presents up to 3 random Leadership members as targets, plus a walk away option.
    35% chance to succeed and steal ingots. 65% chance to fail and lose half the
    attempted amount. Walking away has no consequences.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild

    # Get all members with Leadership role, excluding the user
    leadership_members = [
        member
        for member in interaction.guild.members
        if any(role.name == ROLE.LEADERSHIP for role in member.roles)
        and member.id != interaction.user.id
    ]

    # Check if any targets available
    if not leadership_members:
        embed = handler._build_embed(handler.STEAL_NO_TARGETS)
        return await interaction.followup.send(embed=embed)

    # Select up to 3 random targets
    num_targets = min(3, len(leadership_members))
    targets = random.sample(leadership_members, num_targets)

    # Generate steal amount
    quantity = random.randrange(LOW_INGOT_MIN, HIGH_INGOT_MAX, 1)
    penalty = quantity // 2  # Half the amount if caught

    # Check if user has enough ingots to risk the penalty
    async with db.get_session() as session:
        member_service = MemberService(session)
        user_member = await member_service.get_member_by_discord_id(
            interaction.user.id
        )

        if user_member and user_member.ingots < penalty:
            message = handler.STEAL_USER_NO_INGOTS.format(
                ingot_icon=handler.ingot_icon, penalty=penalty
            )
            embed = handler._build_embed(message)
            return await interaction.followup.send(embed=embed)

    # Create offer message
    offer_message = handler.STEAL_OFFER.format(
        ingot_icon=handler.ingot_icon, amount=quantity, penalty=penalty
    )
    embed = handler._build_embed(offer_message)

    # Create and send the view with target buttons + walk away button
    view = StealTargetView(handler, interaction.user.id, quantity, targets)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message


async def process_steal(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
    amount: int,
    target: discord.Member,
) -> None:
    """Process the result of a steal attempt.

    35% chance to succeed (steal from target).
    65% chance to fail (lose half the amount as penalty).

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
        amount: The amount of ingots to attempt to steal.
        target: The target member to steal from.
    """
    assert interaction.guild

    # Roll for success (35% chance)
    success = random.random() < 0.35

    if success:
        # Check target's ingots
        async with db.get_session() as session:
            member_service = MemberService(session)
            target_member = await member_service.get_member_by_discord_id(target.id)

            if not target_member or target_member.ingots == 0:
                # Target has no ingots
                message = handler.STEAL_TARGET_NO_INGOTS.format(
                    target_mention=target.mention
                )
                embed = handler._build_embed(message)
                return await interaction.followup.send(embed=embed)

            # Cap amount at target's balance
            actual_amount = min(amount, target_member.ingots)

        # Remove from target
        await handler._adjust_ingots(interaction, -actual_amount, target)

        # Add to user
        user_new_total = await handler._adjust_ingots(
            interaction,
            actual_amount,
            interaction.guild.get_member(interaction.user.id),
        )

        if user_new_total is None:
            # Error occurred, but target already lost ingots
            logger.error("Error adding stolen ingots to user")
            return

        # Success message
        message = handler.STEAL_SUCCESS.format(
            ingot_icon=handler.ingot_icon,
            amount=actual_amount,
            target_mention=target.mention,
        )
        message += handler._get_balance_message(
            interaction.user.display_name, user_new_total
        )

    else:
        # Failed - user loses penalty (half the amount)
        penalty = amount // 2

        user_new_total = await handler._adjust_ingots(
            interaction,
            -penalty,
            interaction.guild.get_member(interaction.user.id),
        )

        if user_new_total is None:
            # User somehow lost their ingots between check and now
            logger.error("Error removing penalty from user")
            return

        # Failure message
        message = handler.STEAL_FAILURE.format(
            ingot_icon=handler.ingot_icon,
            amount=amount,
            target_mention=target.mention,
            penalty=penalty,
        )
        message += handler._get_balance_message(
            interaction.user.display_name, user_new_total
        )

    embed = handler._build_embed(message)
    await interaction.followup.send(embed=embed)
