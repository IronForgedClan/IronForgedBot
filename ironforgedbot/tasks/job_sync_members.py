import io
import logging
import time
from datetime import datetime, timezone

import discord
from tabulate import tabulate

from ironforgedbot.commands.admin.sync_members import sync_members
from ironforgedbot.common.helpers import datetime_to_discord_relative
from ironforgedbot.common.text_formatters import text_h2

logger = logging.getLogger(__name__)


async def job_sync_members(
    guild: discord.Guild,
    report_channel: discord.TextChannel,
):
    now = datetime.now(timezone.utc)
    start_time = time.perf_counter()

    try:
        members_change = await sync_members(guild)
    except Exception:
        return await report_channel.send(
            "An unhandled error occurrend during member sync. Please check the logs."
        )

    if len(members_change) < 1:
        return await report_channel.send("**Member Sync**: No changes to report.")

    output_table = tabulate(
        members_change, headers=["Member", "Action", "Reason"], tablefmt="simple"
    )

    discord_file = discord.File(
        fp=io.BytesIO(output_table.encode("utf-8")),
        filename=f"sync_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt",
    )

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    return await report_channel.send(
        f"{text_h2(" 🔁 Member Synchronization")}\n"
        f"Initiated at {datetime_to_discord_relative(now, 't')} and "
        f"completed in **{elapsed_time:.4f}** seconds.",
        file=discord_file,
    )
