import logging

import discord

from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.job_check_activity import job_check_activity

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_check_activity(
    interaction: discord.Interaction, report_channel: discord.TextChannel
):
    """Execute member activity check job manually."""
    await interaction.response.send_message(
        "## Manually initiating activity check job...\n"
        f"View <#{report_channel.id}> for output.",
        ephemeral=True,
    )

    await job_check_activity(report_channel)
