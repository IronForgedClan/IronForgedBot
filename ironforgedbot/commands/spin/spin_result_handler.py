import asyncio
import logging

import discord

from ironforgedbot.common.text_formatting import pad_winner_text

logger = logging.getLogger(__name__)


async def send_spin_result(
    interaction: discord.Interaction,
    file: discord.File,
    winner: str,
    *,
    spin_type: str,
    emoji: str | None = None,
    use_padding: bool = False,
    reactions: list[str] | None = None,
) -> None:
    """Send spin result with configurable delayed spoiler reveal."""

    msg = await interaction.channel.send(
        file=file,
        content=f"-# _spinning **{spin_type}**..._",
    )

    if reactions:
        for reaction in reactions:
            await msg.add_reaction(reaction)

    await asyncio.sleep(10.5)

    try:
        if use_padding:
            padded_winner = pad_winner_text(emoji or "", winner)
            content = f"-# _the next **{spin_type}** is..._\n# ||{padded_winner}||"
        else:
            winner_text = f"{emoji} {winner}" if emoji else winner
            content = f"-# _the next **{spin_type}** is..._\n# ||{winner_text}||"

        await msg.edit(content=content)
    except discord.NotFound:
        logger.warning(f"Could not edit {spin_type} spin message - message was deleted")
    except discord.HTTPException as e:
        logger.error(f"Failed to edit {spin_type} spin message: {e}")
