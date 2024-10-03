import asyncio
import logging
import sys
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord

from ironforgedbot.event_emitter import event_emitter
from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.check_activity import (
    job_check_activity,
    job_check_activity_reminder,
)
from ironforgedbot.tasks.membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.refresh_ranks import job_refresh_ranks
from ironforgedbot.tasks.sync_members import job_sync_members

logger = logging.getLogger(__name__)


class IronForgedAutomations:
    def __init__(self, discord_guild: Optional[discord.Guild]):
        self.loop = asyncio.get_event_loop()
        self.scheduler = AsyncIOScheduler()
        self.discord_guild = discord_guild
        self.report_channel = get_text_channel(
            self.discord_guild, CONFIG.AUTOMATION_CHANNEL_ID
        )

        if not self.report_channel:
            logger.critical(
                f"Error getting automation report channel: {CONFIG.AUTOMATION_CHANNEL_ID}"
            )
            sys.exit(1)

        asyncio.create_task(self.setup_automations())

        event_emitter.on("shutdown", self.cleanup)

    async def cleanup(self):
        logger.info("Clearing all jobs...")
        await self.report_channel.send("Shutting down...")
        self.scheduler.remove_all_jobs()

    async def setup_automations(self):
        self.scheduler.add_job(
            job_sync_members,
            # CronTrigger(minute="*"),
            CronTrigger(hour="*/3", minute=50, second=0, timezone="UTC"),
            args=[self.discord_guild, self.report_channel],
        )

        self.scheduler.add_job(
            job_refresh_ranks,
            CronTrigger(hour=2, minute=0, second=0, timezone="UTC"),
            args=[self.discord_guild, self.report_channel],
        )

        self.scheduler.add_job(
            job_check_activity_reminder,
            CronTrigger(day_of_week="mon", hour=0, minute=0, second=0, timezone="UTC"),
            args=[self.report_channel],
        )

        self.scheduler.add_job(
            job_check_activity,
            CronTrigger(day_of_week="mon", hour=1, minute=0, second=0, timezone="UTC"),
            args=[
                self.report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ],
        )

        self.scheduler.add_job(
            job_check_membership_discrepancies,
            CronTrigger(day_of_week="sun", hour=0, minute=0, second=0, timezone="UTC"),
            args=[
                self.discord_guild,
                self.report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ],
        )

        await self.start()

    async def start(self):
        self.scheduler.start()

        await self.report_channel.send(
            f"🟢 Bot **v{CONFIG.BOT_VERSION}** is **online** and configured to use this channel for"
            f" **{len(self.scheduler.get_jobs())}** automation reports. View pinned message for details."
        )
