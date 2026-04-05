import asyncio
import logging

import discord

from ironforgedbot.common.text_formatting import pad_winner_text

logger = logging.getLogger(__name__)

# Strong references to background tasks to prevent premature GC.
# Tasks are discarded automatically via done callback when they complete.
_background_tasks: set[asyncio.Task] = set()


async def send_spin_result(
    interaction: discord.Interaction,
    file: discord.File,
    winner: str,
    spinning_text: str | None = None,
    winning_text: str | None = None,
    emoji: str | None = None,
    use_padding: bool = False,
    reactions: list[str] | None = None,
) -> None:
    """Send spin result with configurable delayed spoiler reveal."""

    msg = await interaction.channel.send(
        file=file,
        content=f"-# _spinning..._" if not spinning_text else f"-# {spinning_text}",
    )

    if reactions:
        for reaction in reactions:
            await msg.add_reaction(reaction)

    task = asyncio.create_task(
        _delayed_spin_edit(
            interaction=interaction,
            msg=msg,
            winner=winner,
            winning_text=winning_text,
            emoji=emoji,
            use_padding=use_padding,
        ),
        name=f"spin_edit_{msg.id}",
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _delayed_spin_edit(
    interaction: discord.Interaction,
    msg: discord.Message,
    winner: str,
    winning_text: str | None,
    emoji: str | None,
    use_padding: bool,
) -> None:
    """Background task: wait 10.5s then edit message with spoiler winner."""
    try:
        await asyncio.sleep(10.5)

        # Build spoiler content
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
                f"# ||{winner_text}||"
                if not winning_text
                else f"-# {winning_text}\n# ||{winner_text}||"
            )

        await msg.edit(content=content)
        logger.debug(f"Successfully edited spin message {msg.id}")

    except asyncio.CancelledError:
        logger.info(f"Spin edit cancelled for message {msg.id} (likely shutdown)")
        raise
    except discord.NotFound:
        logger.warning(f"Could not edit spin message {msg.id} - message was deleted")
    except discord.HTTPException as e:
        logger.error(f"Failed to edit spin message {msg.id}: {e}")
        try:
            if interaction.channel:
                await interaction.followup.send(
                    f"⚠️ Failed to update spin result in {interaction.channel.mention}: {e}",
                    ephemeral=True,
                )
        except Exception as notify_error:
            logger.error(f"Could not send error notification: {notify_error}")
    except Exception as e:
        logger.error(f"Unexpected error in delayed spin edit for message {msg.id}: {e}")
