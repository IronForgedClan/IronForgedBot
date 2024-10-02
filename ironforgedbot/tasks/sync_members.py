import logging

import discord

from ironforgedbot.commands.admin.cmd_sync_members import sync_members
from ironforgedbot.common.helpers import fit_log_lines_into_discord_messages
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def job_sync_members(
    guild: discord.Guild,
    report_channel: discord.TextChannel,
):
    await report_channel.send("Beginning member sync...")

    try:
        members_change = await sync_members(guild)
    except StorageError as error:
        logger.error(error)
        await report_channel.send("Error syncing members.")

    if len(members_change) == 0:
        await report_channel.send("No changes detected.")
        return

    discord_messages = fit_log_lines_into_discord_messages(members_change)
    for msg in discord_messages:
        await report_channel.send(msg)

    await report_channel.send("Finished member sync.")
