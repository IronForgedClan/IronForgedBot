import asyncio
import logging
import signal
import sys

import discord

from ironforgedbot.state import state
from ironforgedbot.event_emitter import event_emitter
from ironforgedbot.automations import IronForgedAutomations
from ironforgedbot.common.helpers import (
    populate_emoji_cache,
)
from ironforgedbot.config import CONFIG

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

        self.loop = asyncio.get_event_loop()

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

    async def graceful_shutdown(self):
        """Emit the shutdown event and close the bot gracefully."""
        logger.info("Starting graceful shutdown...")
        state.is_shutting_down = True

        if self.automations:
            await self.automations.stop()

        # Emit shutdown event for all services
        await event_emitter.emit("shutdown")

        logger.info("All services cleaned up. Closing Discord connection.")
        await self.close()  # Disconnect the bot from Discord

    async def setup_hook(self):
        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)

        # TODO: Temporary. See function comment for details.
        await populate_emoji_cache(self.application_id or 0, CONFIG.BOT_TOKEN)

    async def on_connect(self):
        logger.info("Bot connected to Discord")

    async def on_reconnect(self):
        logger.info("Bot re-connected to Discord")

    async def on_disconnect(self):
        logger.info("Bot has disconnected from Discord")

    async def on_ready(self):
        if not self.user:
            logger.critical("Error logging into discord server")
            sys.exit(1)

        logger.info(f"Logged in as {self.user.display_name} (ID: {self.user.id})")

        self.automations = IronForgedAutomations(self.get_guild(CONFIG.GUILD_ID))
