import logging

import discord

from ironforgedbot.commands.admin.latest_log import get_latest_log_file
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


async def cmd_view_logs(interaction: discord.Interaction):
    """Send the latest log file."""
    logger.info("Sending latest log file to user...")
    await interaction.response.defer(thinking=True, ephemeral=True)

    file = get_latest_log_file()

    if not file:
        return await send_error_response(interaction, "Error processing log file.")

    return await interaction.followup.send(content="## Latest Log File", file=file)