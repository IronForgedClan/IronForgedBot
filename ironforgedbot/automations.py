import asyncio
import logging
import random
import sys
from typing import Optional, Set

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ironforgedbot.cache.score_cache import SCORE_CACHE
from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.config import CONFIG, ENVIRONMENT
from ironforgedbot.tasks.job_check_activity import (
    job_check_activity,
)
from ironforgedbot.tasks.job_sync_members import job_sync_members
from ironforgedbot.tasks.job_membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks

logger = logging.getLogger(__name__)


class IronForgedAutomations:
    def __init__(self, discord_guild: Optional[discord.Guild]):
        self._running_jobs: Set[asyncio.Task] = set()
        self._job_lock = asyncio.Lock()
        self._shutdown_timeout = 30.0
        self._setup_done = False

        # Configure scheduler with proper executor for async jobs
        from apscheduler.executors.asyncio import AsyncIOExecutor

        executors = {
            "default": AsyncIOExecutor(),
        }
        self.scheduler = AsyncIOScheduler(executors=executors)
        self.scheduler.start()
        logger.debug("Scheduler started successfully")

        report_channel = get_text_channel(discord_guild, CONFIG.AUTOMATION_CHANNEL_ID)

        if not report_channel or not discord_guild:
            logger.critical("Error with automation setup")
            sys.exit(1)

        self.report_channel = report_channel
        self.discord_guild = discord_guild

        asyncio.create_task(self.setup_automations())

    async def stop(self):
        """Initiates shutdown and cleanup of scheduled jobs."""
        logger.info("Initiating shutdown of automations...")

        try:
            self.scheduler.pause()

            await self.wait_for_jobs_to_complete()

            self.scheduler.remove_all_jobs()
            self.scheduler.shutdown(wait=False)

            await self.report_channel.send(
                f"### 🔴 **v{CONFIG.BOT_VERSION}** now offline"
            )
            logger.info("Automation shutdown completed successfully")
        except Exception as e:
            logger.error(f"Error during automation shutdown: {e}")
            raise

    async def wait_for_jobs_to_complete(self):
        """Waits for all active jobs to complete before completing."""
        async with self._job_lock:
            active_jobs = len(self._running_jobs)

            if active_jobs < 1:
                logger.info("No active jobs to wait for...")
                return

            logger.info(f"Waiting for {active_jobs} job(s) to finish...")

            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._running_jobs, return_exceptions=True),
                    timeout=self._shutdown_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout waiting for jobs to complete after {self._shutdown_timeout}s, forcing shutdown"
                )
                for job in self._running_jobs:
                    if not job.done():
                        job.cancel()
                        logger.warning(f"Cancelled job: {job}")
            except Exception as e:
                logger.error(f"Error waiting for jobs to complete: {e}")

    async def track_job(self, job_func, *args, **kwargs):
        """Track a running job by wrapping it in a task and storing the reference."""
        try:
            task = asyncio.create_task(
                self._safe_job_wrapper(job_func, *args, **kwargs)
            )

            async with self._job_lock:
                self._running_jobs.add(task)

            task.add_done_callback(self._job_done_callback)

            logger.debug(f"Started job: {job_func.__name__}")
            return task
        except Exception as e:
            logger.error(f"Error starting job {job_func.__name__}: {e}")
            raise

    def _job_done_callback(self, task: asyncio.Task):
        """Remove the job from the running_jobs set once it is finished."""

        def sync_cleanup():
            """Synchronous cleanup that schedules async work safely."""
            try:
                loop = asyncio.get_running_loop()
                if loop.is_closed():
                    logger.warning("Event loop is closed, skipping job cleanup")
                    return

                async def cleanup():
                    async with self._job_lock:
                        self._running_jobs.discard(task)
                        active_count = len(self._running_jobs)

                    if task.exception():
                        logger.error(
                            f"Job completed with exception: {task.exception()}"
                        )

                    logger.debug(f"Job completed. {active_count} job(s) active.")

                loop.create_task(cleanup())

            except RuntimeError as e:
                logger.warning(f"Could not schedule job cleanup: {e}")

        sync_cleanup()

    def _job_wrapper(self, job_func, *args, **kwargs):
        """Wrapper for tracking active jobs."""

        async def async_wrapper():
            try:
                await self.track_job(job_func, *args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Failed to execute job {job_func.__name__}: {type(e).__name__}: {e}"
                )

        async_wrapper.__name__ = f"{job_func.__name__}_wrapper"
        async_wrapper.__qualname__ = (
            f"IronForgedAutomations.{job_func.__name__}_wrapper"
        )
        return async_wrapper

    async def _safe_job_wrapper(self, job_func, *args, **kwargs):
        """Safely execute a job function with comprehensive error handling."""
        job_name = getattr(job_func, "__name__", str(job_func))

        try:
            logger.debug(f"Starting job: {job_name}")
            await job_func(*args, **kwargs)
            logger.debug(f"Job completed successfully: {job_name}")
        except asyncio.CancelledError:
            logger.warning(f"Job was cancelled: {job_name}")
            raise
        except Exception as e:
            logger.error(
                f"Job failed with exception: {job_name} - {type(e).__name__}: {e}"
            )
            try:
                if hasattr(self, "report_channel") and self.report_channel:
                    await self.report_channel.send(
                        f"⚠️ **Job Error**: `{job_name}` failed with: `{type(e).__name__}: {e}`"
                    )
            except Exception as notification_error:
                logger.error(f"Could not send error notification: {notification_error}")
            raise

    async def _clear_caches(self):
        """Clear expired cache entries and STATE dictionaries."""
        try:
            score_cache_output = await SCORE_CACHE.clean()
            if score_cache_output:
                logger.info(score_cache_output)

            from ironforgedbot.state import STATE
            import time

            expired_count = 0
            current_time = time.time()

            expired_keys = [
                user_id for user_id, offer in STATE.state["double_or_nothing_offers"].items()
                if offer.get("expires_at", 0) < current_time
            ]

            for user_id in expired_keys:
                del STATE.state["double_or_nothing_offers"][user_id]
                expired_count += 1

            if expired_count > 0:
                logger.info(f"Cleared {expired_count} expired double-or-nothing offer(s)")

        except Exception as e:
            logger.error(f"Error clearing caches: {e}")
            raise

    async def setup_automations(self):
        """Add jobs to scheduler."""
        if self._setup_done:
            logger.warning("Automation setup already completed, skipping...")
            return

        offset = (
            0
            if ENVIRONMENT.PRODUCTION in CONFIG.ENVIRONMENT
            else random.randint(10, 50)
        )

        self.scheduler.remove_all_jobs()

        self.scheduler.add_job(
            self._job_wrapper(
                job_sync_members, self.discord_guild, self.report_channel
            ),
            # CronTrigger(minute="*"),
            CronTrigger(hour="3", minute=50, second=offset, timezone="UTC"),
            id="sync_members",
            name="Member Sync Job",
        )

        self.scheduler.add_job(
            self._job_wrapper(
                job_refresh_ranks, self.discord_guild, self.report_channel
            ),
            # CronTrigger(minute="*"),
            CronTrigger(hour="4,16", minute=10, second=offset, timezone="UTC"),
            id="refresh_ranks",
            name="Rank Refresh Job",
        )

        self.scheduler.add_job(
            self._job_wrapper(
                job_check_activity,
                self.report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ),
            # CronTrigger(minute="*"),
            CronTrigger(
                day_of_week="mon", hour=1, minute=0, second=offset, timezone="UTC"
            ),
            id="check_activity",
            name="Activity Check Job",
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
            CronTrigger(
                day_of_week="sun", hour=0, minute=0, second=offset, timezone="UTC"
            ),
            id="check_membership_discrepancies",
            name="Membership Discrepancy Check Job",
        )

        self.scheduler.add_job(
            self._job_wrapper(self._clear_caches),
            CronTrigger(minute="*/10"),
            id="clear_caches",
            name="Cache Cleanup Job",
        )

        await self.report_channel.send(f"### 🟢 **v{CONFIG.BOT_VERSION}** now online")

        await self.track_job(job_sync_members, self.discord_guild, self.report_channel)

        self._setup_done = True
        logger.info("Automation setup completed successfully")
