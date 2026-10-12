import logging

import discord

from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.welcome import send_welcome_messages_with_report
from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_welcome(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    report_channel = get_text_channel(interaction.guild, CONFIG.AUTOMATION_CHANNEL_ID)
    try:
        await send_welcome_messages_with_report(interaction.user, report_channel)
    except discord.Forbidden:
        response = "Unable to DM welcome messages. Check that your DMs are open."
    except Exception:
        logger.exception(f"Unable to send welcome messages to {interaction.user}")
        response = "Unable to send welcome messages. Contact a server administrator."
    else:
        response = "Welcome messages sent to your DMs."

    await interaction.followup.send(response, ephemeral=True)
