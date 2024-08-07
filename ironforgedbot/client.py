import asyncio
import logging
import sys

import discord
from apscheduler.schedulers.background import BackgroundScheduler

from ironforgedbot.config import CONFIG
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.tasks.activity import job_check_activity, job_check_activity_reminder
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
        # Copy commands to the guild (Discord server)
        # TODO: Move this to a separate CLI solely for uploading commands.
        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)

    async def on_ready(self):
        if not self.user:
            logger.critical("Error logging into discord server")
            sys.exit(1)

        logger.info(f"Logged in as {self.user.display_name} (ID: {self.user.id})")

        self.setup_background_jobs()

    def setup_background_jobs(self):
        logger.debug("Initializing background jobs")

        loop = asyncio.get_running_loop()

        self.discord_guild = self.get_guild(self.guild.id)
        scheduler = BackgroundScheduler()

        # Use 'interval' with minutes | seconds = x for testing or next_run_time=datetime.now()
        # from datetime import datetime
        scheduler.add_job(
            job_refresh_ranks,
            "cron",
            args=[self.discord_guild, CONFIG.RANKS_UPDATE_CHANNEL, loop],
            hour=2,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            job_check_activity_reminder,
            "cron",
            args=[self.discord_guild, CONFIG.RANKS_UPDATE_CHANNEL, loop, STORAGE],
            day_of_week="mon",
            hour=0,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            job_check_activity,
            "cron",
            args=[
                self.discord_guild,
                CONFIG.RANKS_UPDATE_CHANNEL,
                loop,
                CONFIG.WOM_API_KEY,
                CONFIG.WOM_GROUP_ID,
                STORAGE,
            ],
            day_of_week="mon",
            hour=1,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            job_sync_members,
            "cron",
            args=[self.discord_guild, CONFIG.RANKS_UPDATE_CHANNEL, loop, STORAGE],
            hour="*/3",
            minute=50,
            second=0,
            timezone="UTC",
        )

        scheduler.start()

        logger.debug("Background jobs ready")
