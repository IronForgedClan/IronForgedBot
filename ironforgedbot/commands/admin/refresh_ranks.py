import logging

import discord

from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks

logger = logging.getLogger(__name__)


async def cmd_refresh_ranks(interaction: discord.Interaction, report_channel: discord.TextChannel):
    """Execute member rank refresh job manually."""
    assert interaction.guild
    
    await interaction.response.send_message(
        "## Manually initiating rank check job...\n"
        f"View <#{report_channel.id}> for output.",
        ephemeral=True,
    )

    logger.info("Manually initiating refresh ranks job")
    await job_refresh_ranks(interaction.guild, report_channel)