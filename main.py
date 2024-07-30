import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401 # isort:skip

import argparse
import logging
import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.command_tree import IronForgedCommands
from ironforgedbot.config import CONFIG
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS
from ironforgedbot.storage.sheets import SheetsStorage
from ironforgedbot.storage.types import IngotsStorage

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A discord bot for Iron Forged.")
    parser.add_argument(
        "--upload_commands",
        action="store_true",
        help="Uploads commands to discord server.",
    )
    args = parser.parse_args()

    # TODO: We lock the bot down with oauth perms; can we shrink intents to match?
    intents = discord.Intents.default()
    intents.members = True
    guild = discord.Object(id=CONFIG.GUILD_ID)

    # set up singleton storage instance
    SheetsStorage.from_account_file("service.json", CONFIG.SHEET_ID)

    # preload data
    if BOSSES and CLUES and RAIDS and SKILLS:
        pass

    client = DiscordClient(
        intents=intents,
        upload=args.upload_commands,
        guild=guild,
        storage=storage_client,
    )
    tree = discord.app_commands.CommandTree(client)

    commands = IronForgedCommands(tree, client, storage_client, args.tmp_dir)
    client.tree = tree

    client.run(CONFIG.BOT_TOKEN)
