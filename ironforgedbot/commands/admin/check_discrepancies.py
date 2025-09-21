import logging

import discord

from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.job_membership_discrepancies import (
    job_check_membership_discrepancies,
)

logger = logging.getLogger(__name__)


async def cmd_check_discrepancies(
    interaction: discord.Interaction, report_channel: discord.TextChannel
):
    """Execute member discrepancy check job manually."""
    assert interaction.guild

    await interaction.response.send_message(
        "## Manually initiating member discrepancy job...\n"
        f"View <#{report_channel.id}> for output.",
        ephemeral=True,
    )

    logger.info("Manually initiating member discrepancy job")
    await job_check_membership_discrepancies(
        interaction.guild,
        report_channel,
        CONFIG.WOM_API_KEY,
        CONFIG.WOM_GROUP_ID,
    )
