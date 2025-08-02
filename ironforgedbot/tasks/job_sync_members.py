import io
import logging
import time
from datetime import datetime, timezone

import discord
from tabulate import tabulate

from ironforgedbot.commands.admin.sync_members import sync_members
from ironforgedbot.common.helpers import datetime_to_discord_relative, format_duration
from ironforgedbot.common.text_formatters import text_h2

logger = logging.getLogger(__name__)


async def job_sync_members(
    guild: discord.Guild,
    report_channel: discord.TextChannel,
):
    now = datetime.now(timezone.utc)
    start_time = time.perf_counter()

    try:
        changes = await sync_members(guild)
    except Exception as e:
        logger.error(e)
        await report_channel.send(
            "🚨 An unhandled error occurrend during member sync. Please check the logs."
        )
        return

    end_time = time.perf_counter()

    if len(changes) < 1:
        await report_channel.send(
            " 🔁 **Member Sync**: No changes. Completed in "
            f"**{format_duration(start_time,end_time)}**. "
        )
        return

    output_table = tabulate(
        changes, headers=["Member", "Action", "Reason"], tablefmt="simple"
    )
    discord_file = discord.File(
        fp=io.BytesIO(output_table.encode("utf-8")),
        filename=f"sync_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt",
    )

    await report_channel.send(
        f"{text_h2(" 🔁 Member Synchronization")}\n"
        f"Initiated at {datetime_to_discord_relative(now, 't')} and "
        f"completed in **{format_duration(start_time, end_time)}**.",
        file=discord_file,
    )
