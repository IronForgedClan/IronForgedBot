import logging

import discord

from ironforgedbot.commands.admin.internal_state import get_internal_state
from ironforgedbot.common.logging_utils import log_command_execution

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_view_state(interaction: discord.Interaction):
    """Send internal bot state."""
    await interaction.response.defer(thinking=True, ephemeral=True)

    file = get_internal_state()

    return await interaction.followup.send(
        content="## Current Internal State", file=file
    )
