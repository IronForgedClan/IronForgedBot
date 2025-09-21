import logging

import discord

from ironforgedbot.commands.admin.internal_state import get_internal_state

logger = logging.getLogger(__name__)


async def cmd_view_state(interaction: discord.Interaction):
    """Send internal bot state."""
    logger.info("Sending internal state to user...")
    await interaction.response.defer(thinking=True, ephemeral=True)

    file = get_internal_state()

    return await interaction.followup.send(
        content="## Current Internal State", file=file
    )
