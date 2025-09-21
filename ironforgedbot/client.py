import asyncio
import logging
import signal
import sys

import discord

from ironforgedbot.automations import IronForgedAutomations
from ironforgedbot.common.helpers import (
    get_text_channel,
    populate_emoji_cache,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG, ENVIRONMENT
from ironforgedbot.effects.add_banned_role import add_banned_role
from ironforgedbot.effects.add_member_role import add_member_role
from ironforgedbot.effects.add_prospect_role import add_prospect_role
from ironforgedbot.effects.nickname_change import nickname_change
from ironforgedbot.effects.remove_member_role import remove_member_role
from ironforgedbot.effects.update_member_rank import update_member_rank
from ironforgedbot.event_emitter import event_emitter
from ironforgedbot.state import STATE
from ironforgedbot.database.database import db

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
        self.automations = None
        self.effect_lock = asyncio.Lock()
        self.loop = asyncio.get_event_loop()
        self._emoji_cache_loaded = False
        self._setup_complete = False

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    @property
    def tree(self):
        return self._tree

    @tree.setter
    def tree(self, value: discord.app_commands.CommandTree):
        self._tree = value

    def handle_signal(self, signum, frame):
        """Signal handler to initiate shutdown."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.loop.call_soon_threadsafe(self.loop.create_task, self.graceful_shutdown())

    def is_discord_internal_task(self, task):
        """Check if task is an internal discord.Client task."""
        coro = task.get_coro()

        if hasattr(coro, "__qualname__"):
            # Internal discord.py task coroutines often have this format.
            if "Client.run.<locals>.runner" in coro.__qualname__:
                return True

        return False

    async def graceful_shutdown(self):
        """Emit the shutdown event and close the bot gracefully."""
        logger.info("Starting graceful shutdown...")
        STATE.state["is_shutting_down"] = True

        pending_tasks = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
            and not self.is_discord_internal_task(task)
        ]

        if pending_tasks:
            logger.info(f"Found {len(pending_tasks)} pending tasks. Waiting...")
            try:
                timeout_seconds = (
                    60 if CONFIG.ENVIRONMENT is ENVIRONMENT.PRODUCTION else 5
                )
                await asyncio.wait_for(
                    asyncio.gather(*pending_tasks, return_exceptions=True),
                    timeout=timeout_seconds,
                )
                logger.info(
                    f"All outstanding tasks completed within the {timeout_seconds}s timeout."
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout occurred while waiting for outstanding tasks.")

        logger.info("Closing database connection...")
        await db.dispose()

        if self.automations:
            await self.automations.stop()

        await event_emitter.emit("shutdown")

        logger.info("All services cleaned up. Closing Discord connection.")
        await self.close()

    async def setup_hook(self):
        """Called only once when the bot starts up, before connecting to Discord."""
        if self._setup_complete:
            logger.debug("Setup hook already completed, skipping...")
            return

        await STATE.load_state()

        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)
            logger.info("Command tree synced to guild")

        # Load emoji cache only once during initial setup
        if not self._emoji_cache_loaded:
            await populate_emoji_cache(await self.fetch_application_emojis())
            self._emoji_cache_loaded = True

        self._setup_complete = True

    async def on_connect(self):
        logger.info("Bot connected to Discord")

    async def on_reconnect(self):
        logger.info("Bot re-connected to Discord")

    async def on_disconnect(self):
        logger.info("Bot has disconnected from Discord")

    async def on_ready(self):
        """Called when the bot has successfully connected to Discord and is ready."""
        if not self.user:
            logger.critical("Error logging into discord server")
            sys.exit(1)

        logger.info(f"Logged in as {self.user.display_name} (ID: {self.user.id})")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="Sea Shanty 2"
            )
        )

        # Only create automations once
        if not self.automations:
            logger.info("Initializing automation system...")
            self.automations = IronForgedAutomations(self.get_guild(CONFIG.GUILD_ID))
        else:
            logger.debug("Automations already initialized, skipping...")

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        async with self.effect_lock:
            report_channel = get_text_channel(
                before.guild, CONFIG.AUTOMATION_CHANNEL_ID
            )
            if not report_channel:
                logger.error("Unable to select report channel")
                return

            if before.nick != after.nick:
                await nickname_change(report_channel, before, after)

            if before.roles == after.roles:
                return

            before_roles = set(r.name for r in before.roles)
            after_roles = set(r.name for r in after.roles)

            roles_added = after_roles - before_roles
            roles_removed = before_roles - after_roles

            if ROLE.MEMBER in roles_added:
                await add_member_role(report_channel, after)

            if ROLE.PROSPECT in roles_added:
                await add_prospect_role(report_channel, after)

            if len(set(RANK.list()) & roles_added) > 0:
                await update_member_rank(report_channel, after)

            if ROLE.MEMBER in roles_removed:
                await remove_member_role(report_channel, after)

            if ROLE.BANNED in roles_added:
                await add_banned_role(report_channel, after)
