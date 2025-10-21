from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


async def result_joke(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Send a random Halloween-themed joke.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    joke = handler._get_random_from_list(handler.JOKES, handler.joke_history)
    content = f"🤡 **Joke**\n\n{joke}"

    await interaction.followup.send(embed=handler._build_embed(content))
