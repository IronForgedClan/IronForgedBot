import logging

import discord

from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.job_check_activity import job_check_activity

logger = logging.getLogger(__name__)


async def cmd_check_activity(interaction: discord.Interaction, report_channel: discord.TextChannel):
    """Execute member activity check job manually."""
    await interaction.response.send_message(
        "## Manually initiating activity check job...\n"
        f"View <#{report_channel.id}> for output.",
        ephemeral=True,
    )

    logger.info("Manually initiating activity check job")
    await job_check_activity(
        report_channel, CONFIG.WOM_API_KEY, CONFIG.WOM_GROUP_ID
    )