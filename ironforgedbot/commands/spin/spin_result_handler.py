import asyncio
import logging

import discord

from ironforgedbot.common.text_formatting import pad_winner_text

logger = logging.getLogger(__name__)


async def send_spin_result(
    interaction: discord.Interaction,
    file: discord.File,
    winner: str,
    spinning_text: str,
    winning_text: str,
    emoji: str | None = None,
    use_padding: bool = False,
    reactions: list[str] | None = None,
) -> None:
    """Send spin result with configurable delayed spoiler reveal"""

    msg = await interaction.channel.send(
        file=file,
        content=f"-# _spinning..._" if not spinning_text else f"-# {spinning_text}",
    )

    if reactions:
        for reaction in reactions:
            await msg.add_reaction(reaction)

    await asyncio.sleep(10.5)

    try:
        if use_padding:
            padded_winner = pad_winner_text(emoji or "", winner)
            content = (
                f"# ||{padded_winner}||"
                if not winning_text
                else f"-# {winning_text}\n# ||{padded_winner}||"
            )
        else:
            winner_text = f"{emoji} {winner}" if emoji else winner
            content = (
                f"#||{winner_text}||"
                if not winning_text
                else f"-# {winning_text}\n# ||{winner_text}||"
            )

        await msg.edit(content=content)
    except discord.NotFound:
        logger.warning("Could not edit spin message - message was deleted")
    except discord.HTTPException as e:
        logger.error(f"Failed to edit spin message: {e}")
