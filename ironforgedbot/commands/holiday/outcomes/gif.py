"""GIF outcome for trick-or-treat."""

import random
from typing import TYPE_CHECKING

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import GIF_HISTORY_LIMIT

if TYPE_CHECKING:
    from ironforgedbot.commands.holiday.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


async def result_gif(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Send a random Halloween-themed GIF.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    chosen_gif = random.choice([s for s in handler.GIFS if s not in handler.gif_history])
    handler._add_to_history(chosen_gif, handler.gif_history, GIF_HISTORY_LIMIT)

    return await interaction.followup.send(chosen_gif)
