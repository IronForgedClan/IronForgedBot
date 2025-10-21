import asyncio
import random
from enum import Enum
from typing import TYPE_CHECKING, Optional

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    BACKROOMS_DOOR_COUNT,
    BACKROOMS_MONSTER_MAX,
    BACKROOMS_MONSTER_MIN,
    BACKROOMS_TREASURE_MAX,
    BACKROOMS_TREASURE_MIN,
)

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


class DoorOutcome(Enum):
    """Possible outcomes behind each door."""

    TREASURE = "treasure"
    MONSTER = "monster"
    ESCAPE = "escape"


OUTCOME_WEIGHTS = {
    DoorOutcome.TREASURE: 0.30,
    DoorOutcome.MONSTER: 0.40,
    DoorOutcome.ESCAPE: 0.30,
}


class BackroomsView(discord.ui.View):
    """Discord UI View for the backrooms corridor selection.

    Displays buttons for each corridor the user can choose from.
    """

    def __init__(
        self,
        handler: "TrickOrTreatHandler",
        user_id: int,
        door_outcomes: list[DoorOutcome],
        door_labels: list[str],
    ):
        """Initialize the backrooms view.

        Args:
            handler: The TrickOrTreatHandler instance to use for processing the result.
            user_id: The Discord user ID who can interact with this view.
            door_outcomes: List of outcomes for each corridor (in order).
            door_labels: List of selected corridor labels to display.
        """
        super().__init__(timeout=45.0)
        self.handler = handler
        self.user_id = user_id
        self.door_outcomes = door_outcomes
        self.door_labels = door_labels
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        for i in range(BACKROOMS_DOOR_COUNT):
            button = discord.ui.Button(
                label=door_labels[i],
                style=discord.ButtonStyle.secondary,
                custom_id=f"backrooms_door_{i}",
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
                    "These aren't your backrooms!", ephemeral=True
                )
                return

            if self.has_interacted:
                await interaction.response.send_message(
                    "You already chose a corridor!", ephemeral=True
                )
                return

            self.has_interacted = True

            await interaction.response.defer()

            door_label = self.door_labels[door_index]
            suspense_message = self.handler.backrooms["OPENING_DOOR"].format(
                door=door_label
            )
            suspense_embed = self.handler._build_embed(
                suspense_message,
                self.handler.backrooms_thumbnails,
                self.handler.backrooms_thumbnail_history,
            )
            if self.message:
                await self.message.edit(embed=suspense_embed, view=None)

            await asyncio.sleep(2)

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
                    self.handler.backrooms["EXPIRED_MESSAGE"],
                    self.handler.backrooms_thumbnails,
                    self.handler.backrooms_thumbnail_history,
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

    user_nickname, _ = await handler._get_user_info(interaction.user.id)

    match outcome:
        case DoorOutcome.TREASURE:
            amount = random.randint(BACKROOMS_TREASURE_MIN, BACKROOMS_TREASURE_MAX)
            message = random.choice(handler.backrooms["TREASURE_MESSAGES"])

            ingot_total = await handler._adjust_ingots(
                interaction,
                amount,
                interaction.guild.get_member(interaction.user.id),
                reason="Trick or treat: backrooms treasure",
            )

            if ingot_total is not None:
                formatted_message = message.format(
                    ingots=f"{handler.ingot_icon}{amount:,}"
                )
                formatted_message += handler._get_balance_message(
                    user_nickname, ingot_total
                )
                embed = handler._build_embed(
                    formatted_message,
                    handler.backrooms_thumbnails,
                    handler.backrooms_thumbnail_history,
                )
                await interaction.followup.send(embed=embed)

        case DoorOutcome.MONSTER:
            amount = random.randint(BACKROOMS_MONSTER_MIN, BACKROOMS_MONSTER_MAX)
            message = random.choice(handler.backrooms["MONSTER_MESSAGES"])

            ingot_total = await handler._adjust_ingots(
                interaction,
                -amount,
                interaction.guild.get_member(interaction.user.id),
                reason="Trick or treat: backrooms entity",
            )

            if ingot_total is None:
                lucky_message = random.choice(
                    handler.backrooms["LUCKY_ESCAPE_MESSAGES"]
                )
                lucky_message += handler._get_balance_message(user_nickname, 0)
                embed = handler._build_embed(
                    lucky_message,
                    handler.backrooms_thumbnails,
                    handler.backrooms_thumbnail_history,
                )
                await interaction.followup.send(embed=embed)
            else:
                formatted_message = message.format(
                    ingots=f"{handler.ingot_icon}-{amount:,}"
                )
                formatted_message += handler._get_balance_message(
                    user_nickname, ingot_total
                )
                embed = handler._build_embed(
                    formatted_message,
                    handler.backrooms_thumbnails,
                    handler.backrooms_thumbnail_history,
                )
                await interaction.followup.send(embed=embed)

        case DoorOutcome.ESCAPE:
            message = random.choice(handler.backrooms["ESCAPE_MESSAGES"])
            embed = handler._build_embed(
                message,
                handler.backrooms_thumbnails,
                handler.backrooms_thumbnail_history,
            )
            await interaction.followup.send(embed=embed)


async def result_backrooms(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Handle the backrooms outcome.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction.
    """
    outcome_choices = list(OUTCOME_WEIGHTS.keys())
    outcome_probabilities = list(OUTCOME_WEIGHTS.values())
    outcomes = random.choices(
        outcome_choices, weights=outcome_probabilities, k=BACKROOMS_DOOR_COUNT
    )

    selected_labels = random.sample(handler.backrooms_door_labels, BACKROOMS_DOOR_COUNT)

    expires_timestamp = f"<t:{int(interaction.created_at.timestamp()) + 45}:R>"
    intro_message = handler.backrooms["INTRO"].format(expires=expires_timestamp)

    embed = handler._build_embed(
        intro_message, handler.backrooms_thumbnails, handler.backrooms_thumbnail_history
    )

    view = BackroomsView(handler, interaction.user.id, outcomes, selected_labels)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message
