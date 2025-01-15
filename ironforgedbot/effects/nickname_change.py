import logging
import discord

from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.tasks.job_sync_members import job_sync_members

logger = logging.getLogger(__name__)


async def nickname_change(
    report_channel: discord.TextChannel, before: discord.Member, after: discord.Member
):
    await report_channel.send(
        f":information: Name change detected: {text_bold(before.display_name)} → "
        f"{text_bold(after.display_name)}. Initiating member sync..."
    )

    await job_sync_members(report_channel.guild, report_channel)
