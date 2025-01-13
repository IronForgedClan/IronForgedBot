import asyncio
import logging
import sys
from typing import Optional

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.job_check_activity import (
    job_check_activity,
    job_check_activity_reminder,
)
from ironforgedbot.tasks.job_sync_members import job_sync_members
from ironforgedbot.tasks.job_membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks

logger = logging.getLogger(__name__)


class IronForgedAutomations:
    def __init__(self, discord_guild: Optional[discord.Guild]):
        self.loop = asyncio.get_event_loop()
        self.running_jobs = []
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()

        report_channel = get_text_channel(discord_guild, CONFIG.AUTOMATION_CHANNEL_ID)

        if not report_channel or not discord_guild:
            logger.critical("Error with automation setup")
            sys.exit(1)

        self.report_channel = report_channel
        self.discord_guild = discord_guild

        asyncio.create_task(self.setup_automations())

    async def stop(self):
        """Initiates shutdown and cleanup of scheduled jobs."""
        self.scheduler.pause()
        await self.wait_for_jobs_to_complete()
        self.scheduler.remove_all_jobs()
        await self.report_channel.send("🔴 Bot shutting down...")

    async def wait_for_jobs_to_complete(self):
        """Waits for all active jobs to complete before completing."""
        active_jobs = len(self.running_jobs)

        if active_jobs < 1:
            logger.info("No active jobs to wait for...")
            return

        logger.info(f"Waiting for {active_jobs} job(s) to finish...")
        await asyncio.gather(*self.running_jobs)

    def track_job(self, job_func, *args, **kwargs):
        """Track a running job by wrapping it in a task and storing the reference."""
        task = self.loop.create_task(job_func(*args, **kwargs))
        self.running_jobs.append(task)
        task.add_done_callback(self.job_done)  # Cleanup once the job is done
        return task

    def job_done(self, task):
        """Remove the job from the running_jobs list once it is finished."""
        self.running_jobs.remove(task)
        logger.info(f"A job has completed. {len(self.running_jobs)} job(s) active.")

    def _job_wrapper(self, job_func, *args, **kwargs):
        """Wrapper for tracking active jobs."""
        return lambda: self.track_job(job_func, *args, **kwargs)

    async def setup_automations(self):
        """Add jobs to scheduler."""
        self.scheduler.add_job(
            self._job_wrapper(
                job_sync_members, self.discord_guild, self.report_channel
            ),
            # CronTrigger(minute="*"),
            CronTrigger(hour="*/3", minute=50, second=0, timezone="UTC"),
        )

        self.scheduler.add_job(
            self._job_wrapper(
                job_refresh_ranks, self.discord_guild, self.report_channel
            ),
            # CronTrigger(minute="*"),
            CronTrigger(hour="8,20", minute=0, second=0, timezone="UTC"),
        )

        self.scheduler.add_job(
            self._job_wrapper(job_check_activity_reminder, self.report_channel),
            # CronTrigger(minute="*"),
            CronTrigger(day_of_week="mon", hour=0, minute=0, second=0, timezone="UTC"),
        )

        self.scheduler.add_job(
            self._job_wrapper(
                job_check_activity,
                self.report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ),
            # CronTrigger(minute="*"),
            CronTrigger(day_of_week="mon", hour=1, minute=0, second=0, timezone="UTC"),
        )

        self.scheduler.add_job(
            self._job_wrapper(
                job_check_membership_discrepancies,
                self.discord_guild,
                self.report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ),
            # CronTrigger(minute="*"),
            CronTrigger(day_of_week="sun", hour=0, minute=0, second=0, timezone="UTC"),
        )

        await self.report_channel.send(
            f"🟢 Bot **v{CONFIG.BOT_VERSION}** is **online** and configured to use this channel for"
            f" **{len(self.scheduler.get_jobs())}** automation reports. View pinned message for details."
        )
