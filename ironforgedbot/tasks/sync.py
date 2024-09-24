import logging

import discord

from ironforgedbot.commands.admin.cmd_sync_members import sync_members
from ironforgedbot.common.helpers import fit_log_lines_into_discord_messages
from ironforgedbot.storage.types import StorageError
from ironforgedbot.tasks import _send_discord_message_plain, can_start_task

logger = logging.getLogger(__name__)


async def job_sync_members(
    guild: discord.Guild,
    updates_channel_name: str,
):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Miss-configured task sync_members")
        return

    lines = []

    try:
        lines = sync_members(guild)
    except StorageError as error:
        error_message = f"Encountered error syncing members: {error}"
        logger.error(error_message)
        await _send_discord_message_plain(updates_channel, error_message)

    if 0 == len(lines):
        return

    await _send_discord_message_plain(updates_channel, "Finished sync members job")

    discord_messages = fit_log_lines_into_discord_messages(lines)
    for msg in discord_messages:
        await _send_discord_message_plain(updates_channel, msg)
