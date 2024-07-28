import asyncio
import logging
import sys
from apscheduler.schedulers.background import BackgroundScheduler
import discord

from ironforgedbot.storage.types import IngotsStorage
from ironforgedbot.tasks.activity import check_activity, check_activity_reminder
from ironforgedbot.tasks.ranks import refresh_ranks

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
        ranks_update_channel: str,
        wom_api_key: str,
        wom_group_id: int,
        storage: IngotsStorage,
    ):
        super().__init__(intents=intents)
        self.discord_guild = None
        self.upload = upload
        self.guild = guild
        self.ranks_update_channel = ranks_update_channel
        self.wom_api_key = wom_api_key
        self.wom_group_id = wom_group_id
        self.storage = storage

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
            sys.exit()

        logger.info(f"Logged in as {self.user.display_name} (ID: {self.user.id})")

        # Starting background jobs
        loop = asyncio.get_running_loop()

        self.discord_guild = self.get_guild(self.guild.id)
        scheduler = BackgroundScheduler()

        # Use 'interval' with minutes | seconds = x for testing or next_run_time=datetime.now()
        # from datetime import datetime
        scheduler.add_job(
            refresh_ranks,
            "cron",
            args=[self.discord_guild, self.ranks_update_channel, loop],
            hour=2,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            check_activity_reminder,
            "cron",
            args=[self.discord_guild, self.ranks_update_channel, loop, self.storage],
            day_of_week="mon",
            hour=0,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            check_activity,
            "cron",
            args=[
                self.discord_guild,
                self.ranks_update_channel,
                loop,
                self.wom_api_key,
                self.wom_group_id,
                self.storage,
            ],
            day_of_week="mon",
            hour=1,
            minute=0,
            second=0,
            timezone="UTC",
        )
        scheduler.start()