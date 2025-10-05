"""Haunted house outcome for trick-or-treat."""

import asyncio
import random
from enum import Enum
from typing import TYPE_CHECKING, Optional

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    HAUNTED_HOUSE_DOOR_COUNT,
    HAUNTED_HOUSE_MONSTER_MAX,
    HAUNTED_HOUSE_MONSTER_MIN,
    HAUNTED_HOUSE_TREASURE_MAX,
    HAUNTED_HOUSE_TREASURE_MIN,
)
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService

if TYPE_CHECKING:
    from ironforgedbot.commands.holiday.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


class DoorOutcome(Enum):
    """Possible outcomes behind each door."""

    TREASURE = "treasure"
    MONSTER = "monster"
    ESCAPE = "escape"


# Weighted probabilities for door outcomes
OUTCOME_WEIGHTS = {
    DoorOutcome.TREASURE: 0.30,  # 30%
    DoorOutcome.MONSTER: 0.40,  # 40%
    DoorOutcome.ESCAPE: 0.30,  # 30%
}


class HauntedHouseView(discord.ui.View):
    """Discord UI View for the haunted house door selection.

    Displays buttons for each door the user can choose from.
    The view times out after 45 seconds.
    """

    def __init__(
        self,
        handler: "TrickOrTreatHandler",
        user_id: int,
        door_outcomes: list[DoorOutcome],
        door_labels: list[str],
    ):
        """Initialize the haunted house view.

        Args:
            handler: The TrickOrTreatHandler instance to use for processing the result.
            user_id: The Discord user ID who can interact with this view.
            door_outcomes: List of outcomes for each door (in order).
            door_labels: List of selected door labels to display.
        """
        super().__init__(timeout=45.0)
        self.handler = handler
        self.user_id = user_id
        self.door_outcomes = door_outcomes
        self.door_labels = door_labels
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        for i in range(HAUNTED_HOUSE_DOOR_COUNT):
            button = discord.ui.Button(
                label=door_labels[i],
                style=discord.ButtonStyle.secondary,
                custom_id=f"haunted_house_door_{i}",
                row=0,
            )
            button.callback = self._create_door_callback(i)
            self.add_item(button)

    def _create_door_callback(self, door_index: int):
        """Create a callback function for a specific door button.

        Args:
            door_index: The index of the door (0-2).

        Returns:
            An async callback function for the button.
        """

        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This isn't your haunted house!", ephemeral=True
                )
                return

            if self.has_interacted:
                await interaction.response.send_message(
                    "You already chose a door!", ephemeral=True
                )
                return

            self.has_interacted = True

            await interaction.response.defer()

            # Show suspense message with specific door being opened
            door_label = self.door_labels[door_index]
            suspense_message = self.handler.HAUNTED_HOUSE_OPENING_DOOR.format(
                door=door_label
            )
            suspense_embed = self.handler._build_embed(suspense_message)
            if self.message:
                await self.message.edit(embed=suspense_embed, view=None)

            # Wait for suspense
            await asyncio.sleep(2)

            # Delete the suspense message
            if self.message:
                await self.message.delete()

            outcome = self.door_outcomes[door_index]
            await process_door_choice(
                self.handler,
                interaction,
                outcome,
                door_index,
                self.door_outcomes,
                self.door_labels,
            )

            self.stop()

        return callback

    async def on_timeout(self):
        """Handle view timeout."""
        if self.has_interacted:
            return

        if self.message:
            try:
                embed = self.handler._build_embed(
                    self.handler.HAUNTED_HOUSE_EXPIRED_MESSAGE
                )
                await self.message.edit(embed=embed, view=None)
            except discord.HTTPException:
                pass


async def process_door_choice(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
    outcome: DoorOutcome,
    chosen_index: int,
    door_outcomes: list[DoorOutcome],
    door_labels: list[str],
) -> None:
    """Process the user's door choice and apply the outcome.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction.
        outcome: The outcome behind the chosen door.
        chosen_index: The index of the door chosen.
        door_outcomes: List of all door outcomes.
        door_labels: List of all door labels.
    """
    assert interaction.guild

    async with db.get_session() as session:
        member_service = MemberService(session)
        user_member = await member_service.get_member_by_discord_id(interaction.user.id)
        user_nickname = user_member.nickname if user_member else "User"

    match outcome:
        case DoorOutcome.TREASURE:
            # Win ingots
            amount = random.randint(
                HAUNTED_HOUSE_TREASURE_MIN, HAUNTED_HOUSE_TREASURE_MAX
            )
            message = random.choice(handler.HAUNTED_HOUSE_TREASURE_MESSAGES)

            ingot_total = await handler._adjust_ingots(
                interaction,
                amount,
                interaction.guild.get_member(interaction.user.id),
                reason="Trick or treat: haunted house treasure",
            )

            if ingot_total is not None:
                formatted_message = message.format(
                    ingots=f"{handler.ingot_icon}{amount:,}"
                )
                formatted_message += handler._get_balance_message(
                    user_nickname, ingot_total
                )
                embed = handler._build_embed(formatted_message)
                await interaction.followup.send(embed=embed)

        case DoorOutcome.MONSTER:
            # Lose ingots
            amount = random.randint(
                HAUNTED_HOUSE_MONSTER_MIN, HAUNTED_HOUSE_MONSTER_MAX
            )
            message = random.choice(handler.HAUNTED_HOUSE_MONSTER_MESSAGES)

            ingot_total = await handler._adjust_ingots(
                interaction,
                -amount,
                interaction.guild.get_member(interaction.user.id),
                reason="Trick or treat: haunted house monster",
            )

            if ingot_total is None:
                # User has no ingots to lose - lucky escape!
                lucky_message = random.choice(handler.HAUNTED_HOUSE_LUCKY_ESCAPE_MESSAGES)
                lucky_message += handler._get_balance_message(user_nickname, 0)
                embed = handler._build_embed(lucky_message)
                await interaction.followup.send(embed=embed)
            else:
                formatted_message = message.format(
                    ingots=f"{handler.ingot_icon}{amount:,}"
                )
                formatted_message += handler._get_balance_message(
                    user_nickname, ingot_total
                )
                embed = handler._build_embed(formatted_message)
                await interaction.followup.send(embed=embed)

        case DoorOutcome.ESCAPE:
            # No ingot change
            message = random.choice(handler.HAUNTED_HOUSE_ESCAPE_MESSAGES)
            embed = handler._build_embed(message)
            await interaction.followup.send(embed=embed)


async def result_haunted_house(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Handle the haunted house outcome.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction.
    """
    # Randomly assign weighted outcomes to doors
    outcome_choices = list(OUTCOME_WEIGHTS.keys())
    outcome_probabilities = list(OUTCOME_WEIGHTS.values())
    outcomes = random.choices(
        outcome_choices, weights=outcome_probabilities, k=HAUNTED_HOUSE_DOOR_COUNT
    )

    # Randomly select 3 door labels from available options
    selected_labels = random.sample(
        handler.HAUNTED_HOUSE_DOOR_LABELS, HAUNTED_HOUSE_DOOR_COUNT
    )

    # Build the intro message with expiry timestamp
    expires_timestamp = f"<t:{int(interaction.created_at.timestamp()) + 45}:R>"
    intro_message = handler.HAUNTED_HOUSE_INTRO.format(expires=expires_timestamp)

    embed = handler._build_embed(intro_message)

    view = HauntedHouseView(handler, interaction.user.id, outcomes, selected_labels)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message
