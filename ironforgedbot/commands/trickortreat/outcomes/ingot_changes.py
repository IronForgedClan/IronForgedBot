"""Ingot addition/removal outcomes for trick-or-treat."""

import random
from typing import TYPE_CHECKING

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    HIGH_INGOT_MIN,
    LOW_INGOT_MAX,
    LOW_INGOT_MIN,
)

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


async def result_add_high(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Add a high amount of ingots to the player.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    quantity = random.randrange(HIGH_INGOT_MIN, HIGH_INGOT_MAX, 1)
    await handler._handle_ingot_result(interaction, quantity, is_positive=True)


async def result_add_low(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Add a low amount of ingots to the player.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    quantity = random.randrange(LOW_INGOT_MIN, LOW_INGOT_MAX, 1)
    await handler._handle_ingot_result(interaction, quantity, is_positive=True)


async def result_remove_high(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Remove a high amount of ingots from the player.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    quantity = random.randrange(HIGH_INGOT_MIN, HIGH_INGOT_MAX, 1) * -1
    await handler._handle_ingot_result(interaction, quantity, is_positive=False)


async def result_remove_low(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Remove a low amount of ingots from the player.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    quantity = random.randrange(LOW_INGOT_MIN, LOW_INGOT_MAX, 1) * -1
    await handler._handle_ingot_result(interaction, quantity, is_positive=False)
