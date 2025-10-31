from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
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
    chosen_gif = handler._get_random_from_list(handler.gifs, handler.history["gif"])

    return await interaction.followup.send(chosen_gif)
