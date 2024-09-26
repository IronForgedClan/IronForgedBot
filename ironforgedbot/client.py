import logging
import sys

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ironforgedbot.common.helpers import get_text_channel, populate_emoji_cache
from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.activity import job_check_activity, job_check_activity_reminder
from ironforgedbot.tasks.membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.ranks import job_refresh_ranks
from ironforgedbot.tasks.sync import job_sync_members

logging.getLogger("discord").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


class DiscordClient(discord.Client):
    """Client class for bot to handle slashcommands.

    There is a chicken&egg relationship between a discord client & the
    command tree. The tree needs a client during init, but the easiest
    way to upload commands is during client.setup_hook. So, initialize
    the client first, then the tree, then add the tree property before
    calling client.run.

    intents = discord.Intents.default()
    guild = discord.Object(id=$ID)
    client = DiscordClient(intents=intents, upload=true, guild=guild)
    tree = BuildCommandTree(client)
    client.tree = tree

    client.run('token')

    Attributes:
        upload: Whether or not to upload commands to guild.
        guild: Guild for this client to upload commands to.
        tree: CommandTree to use for uploading commands.
    """

    def __init__(
        self,
        *,
        intents: discord.Intents,
        upload: bool,
        guild: discord.Object,
    ):
        super().__init__(intents=intents)
        self.discord_guild = None
        self.upload = upload
        self.guild = guild

    @property
    def tree(self):
        return self._tree

    @tree.setter
    def tree(self, value: discord.app_commands.CommandTree):
        self._tree = value

    async def setup_hook(self):
        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)

        # TODO: Temporary. See function comment for details.
        populate_emoji_cache(self.application_id or 0, CONFIG.BOT_TOKEN)

    async def on_ready(self):
        if not self.user:
            logger.critical("Error logging into discord server")
            sys.exit(1)

        logger.info(f"Logged in as {self.user.display_name} (ID: {self.user.id})")

        await self.setup_background_jobs()

    async def setup_background_jobs(self):
        discord_guild = self.get_guild(self.guild.id)
        report_channel = get_text_channel(discord_guild, CONFIG.AUTOMATION_CHANNEL_ID)

        if not report_channel:
            logger.critical(
                f"Error getting automation report channel: {CONFIG.AUTOMATION_CHANNEL_ID}"
            )
            sys.exit(1)

        scheduler = AsyncIOScheduler()

        scheduler.add_job(
            job_sync_members,
            CronTrigger(hour="*/3", minute=50, second=0, timezone="UTC"),
            args=[discord_guild, report_channel],
        )

        scheduler.add_job(
            job_refresh_ranks,
            CronTrigger(hour=2, minute=0, second=0, timezone="UTC"),
            args=[discord_guild, report_channel],
        )

        scheduler.add_job(
            job_check_activity_reminder,
            CronTrigger(day_of_week="mon", hour=0, minute=0, second=0, timezone="UTC"),
            args=[report_channel],
        )

        scheduler.add_job(
            job_check_activity,
            CronTrigger(day_of_week="mon", hour=1, minute=0, second=0, timezone="UTC"),
            args=[
                report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ],
        )

        scheduler.add_job(
            job_check_membership_discrepancies,
            CronTrigger(day_of_week="sun", hour=0, minute=0, second=0, timezone="UTC"),
            args=[
                discord_guild,
                report_channel,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
            ],
        )

        scheduler.start()

        await report_channel.send(
            f"Bot **v{CONFIG.BOT_VERSION}** is online and configured to use this channel for automation reports."
        )
