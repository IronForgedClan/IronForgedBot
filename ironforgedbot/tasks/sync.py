import asyncio
import logging

import discord

from ironforgedbot.commands.syncmembers.syncmembers import sync_members
from ironforgedbot.common.helpers import fit_log_lines_into_discord_messages
from ironforgedbot.storage.types import IngotsStorage, StorageError
from ironforgedbot.tasks import can_start_task, _send_discord_message_plain

logger = logging.getLogger(__name__)


def job_sync_members(guild: discord.Guild,
                     updates_channel_name: str,
                     loop: asyncio.BaseEventLoop,
                     storage: IngotsStorage):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Miss-configured task sync_members")
        return

    lines = []

    try:
        lines = sync_members(guild, storage)
    except StorageError as error:
        error_message = f"Encountered error syncing members: {error}"
        logger.error(error_message)
        asyncio.run_coroutine_threadsafe(_send_discord_message_plain(updates_channel, error_message), loop)

    if 0 == len(lines):
        return

    asyncio.run_coroutine_threadsafe(_send_discord_message_plain(updates_channel, "Finished sync members job"),
                                     loop)

    discord_messages = fit_log_lines_into_discord_messages(lines)
    for msg in discord_messages:
        asyncio.run_coroutine_threadsafe(_send_discord_message_plain(updates_channel, msg), loop)