import logging
import random
import time
from typing import TYPE_CHECKING, List, Optional

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    LOW_INGOT_MIN,
)
from ironforgedbot.common.roles import ROLE
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )

logger = logging.getLogger(__name__)


def _calculate_steal_penalty(amount: int) -> int:
    """Calculate the penalty for a failed steal attempt.

    Args:
        amount: The amount of ingots attempted to steal.

    Returns:
        The penalty amount (3/4 of amount, rounded up to nearest 100).
    """
    penalty_raw = (amount * 3 + 3) // 4
    return ((penalty_raw + 99) // 100) * 100


def _get_steal_success_rate(target_ingots: int) -> float:
    """Calculate steal success rate based on target's ingot balance.

    Args:
        target_ingots: The number of ingots the target has.

    Returns:
        The probability of success (0.0-1.0).
    """
    if target_ingots < 25_000:
        return 0
    elif target_ingots < 50_000:
        return 0.05
    elif target_ingots < 100_000:
        return 0.25
    elif target_ingots < 250_000:
        return 0.30
    elif target_ingots < 500_000:
        return 0.35
    elif target_ingots < 2_000_000:
        return 0.40
    else:
        return 0.45


class StealTargetView(discord.ui.View):
    """Discord UI View for the steal target selection.

    Displays buttons for each member that can be stolen from,
    plus a "Walk Away" button to abort safely.
    The view times out after 45 seconds.
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
            targets: List of members to display as targets (max 4).
        """
        super().__init__(timeout=45.0)
        self.handler = handler
        self.user_id = user_id
        self.amount = amount
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        for target in targets:
            button = discord.ui.Button(
                label=target.display_name,
                style=discord.ButtonStyle.secondary,
                custom_id=f"steal_{target.id}",
                row=0,
            )
            button.callback = self._create_steal_callback(target)
            self.add_item(button)

        walk_away_button = discord.ui.Button(
            label="🚶 Walk Away",
            style=discord.ButtonStyle.danger,
            custom_id="steal_walk_away",
            row=1,
        )
        walk_away_button.callback = self._walk_away_callback
        self.add_item(walk_away_button)

    def _cleanup(self) -> None:
        """Clean up references."""
        self.handler = None

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

            await interaction.response.defer()

            self.clear_items()
            embed = await process_steal(self.handler, interaction, self.amount, target)

            if self.message:
                await self.message.edit(embed=embed, view=self)

            self.stop()
            self._cleanup()

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

        await interaction.response.defer()

        self.clear_items()

        embed = self.handler._build_embed(self.handler.steal["walk_away"])

        if self.message:
            await self.message.edit(embed=embed, view=self)

        self.stop()
        self._cleanup()

    async def on_timeout(self):
        """Handle the view timing out after 45 seconds."""
        if self.has_interacted or not self.message:
            self._cleanup()
            return

        # Remove all buttons
        self.clear_items()

        embed = self.handler._build_embed(self.handler.steal["expired"])
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

        self._cleanup()


async def result_steal(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Offer the player a chance to steal ingots from guild members.

    Presents up to 4 random members as targets, plus a walk away option.
    Success rate scales based on target's ingot balance. On failure,
    lose 3/4 of the attempted amount rounded up. Walking away has no consequences.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild

    member_targets = [
        member
        for member in interaction.guild.members
        if any(role.name == ROLE.MEMBER for role in member.roles)
        and member.id != interaction.user.id
    ]

    if not member_targets:
        embed = handler._build_embed(handler.steal["no_targets"])
        return await interaction.followup.send(embed=embed)

    num_targets = min(4, len(member_targets))
    targets = random.sample(member_targets, num_targets)

    quantity = random.randrange(LOW_INGOT_MIN, HIGH_INGOT_MAX, 1)
    penalty = _calculate_steal_penalty(quantity)

    async with db.get_session() as session:
        member_service = MemberService(session)
        user_member = await member_service.get_member_by_discord_id(interaction.user.id)

        if user_member and user_member.ingots < penalty:
            message = handler.steal["user_no_ingots"].format(
                ingot_icon=handler.ingot_icon, penalty=penalty
            )
            embed = handler._build_embed(message)
            return await interaction.followup.send(embed=embed)

    expire_timestamp = int(time.time() + 45)
    expires_formatted = f"<t:{expire_timestamp}:R>"

    offer_message = handler.steal["offer"].format(
        ingot_icon=handler.ingot_icon,
        amount=quantity,
        penalty=penalty,
        expires=expires_formatted,
    )
    embed = handler._build_embed(offer_message)

    view = StealTargetView(handler, interaction.user.id, quantity, targets)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message


async def process_steal(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
    amount: int,
    target: discord.Member,
) -> discord.Embed:
    """Process the result of a steal attempt.

    Success rate scales based on target's ingot balance.

    On failure, lose 3/4 of the amount rounded up as penalty.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
        amount: The amount of ingots to attempt to steal.
        target: The target member to steal from.

    Returns:
        The embed containing the result message.
    """
    assert interaction.guild

    async with db.get_session() as session:
        member_service = MemberService(session)
        target_member = await member_service.get_member_by_discord_id(target.id)

        if not target_member or target_member.ingots == 0:
            message = handler.steal["target_no_ingots"].format(
                target_mention=target.mention
            )
            return handler._build_embed(message)

        success_rate = _get_steal_success_rate(target_member.ingots)

        actual_amount = min(amount, target_member.ingots)

    success = random.random() < success_rate

    if success:
        thief_nickname, _ = await handler._get_user_info(interaction.user.id)

        await handler._adjust_ingots(
            interaction,
            -actual_amount,
            target,
            reason=f"Trick or treat: stolen by {thief_nickname}",
        )

        user_new_total = await handler._adjust_ingots(
            interaction,
            actual_amount,
            interaction.guild.get_member(interaction.user.id),
            reason="Trick or treat: steal success",
        )

        if user_new_total is None:
            logger.error("Error adding stolen ingots to user")
            return handler._build_embed("An error occurred processing the steal.")

        user_nickname, _ = await handler._get_user_info(interaction.user.id)

        message = handler.steal["success"].format(
            ingot_icon=handler.ingot_icon,
            amount=actual_amount,
            target_mention=target.mention,
        )
        message += handler._get_balance_message(user_nickname, user_new_total)

    else:
        penalty = _calculate_steal_penalty(amount)

        user_new_total = await handler._adjust_ingots(
            interaction,
            -penalty,
            interaction.guild.get_member(interaction.user.id),
            reason="Trick or treat: steal failure penalty",
        )

        if user_new_total is None:
            logger.error("Error removing penalty from user")
            return handler._build_embed("An error occurred processing the steal.")

        user_nickname, _ = await handler._get_user_info(interaction.user.id)

        formatted_penalty = f"-{penalty:,}"
        message = handler.steal["failure"].format(
            ingot_icon=handler.ingot_icon,
            amount=amount,
            target_mention=target.mention,
            penalty=formatted_penalty,
        )
        message += handler._get_balance_message(user_nickname, user_new_total)

    return handler._build_embed(message)
