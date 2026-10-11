import logging

import discord

from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.welcome import send_welcome_messages

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_welcome(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    try:
        await send_welcome_messages(interaction.user)
    except discord.Forbidden:
        await interaction.followup.send(
            "Unable to DM welcome messages. Check that your DMs are open.",
            ephemeral=True,
        )
        return
    except Exception:
        logger.exception(f"Unable to send welcome messages to {interaction.user}")
        await interaction.followup.send(
            "Unable to send welcome messages. Contact a server administrator.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        "Welcome messages sent to your DMs.", ephemeral=True
    )
