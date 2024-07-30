import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401 # isort:skip
import argparse
import logging
import os
import sys

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.command_tree import IronForgedCommands
from ironforgedbot.config import CONFIG
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS
from ironforgedbot.storage.sheets import STORAGE

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A discord bot for Iron Forged.")
    parser.add_argument(
        "--upload_commands",
        action="store_true",
        help="Uploads commands to discord server.",
    )
    args = parser.parse_args()

    # Preload hard requirements
    if CONFIG and STORAGE and BOSSES and CLUES and RAIDS and SKILLS:
        pass

    try:
        os.makedirs(CONFIG.TEMP_DIR, exist_ok=True)
    except PermissionError:
        logging.critical(f"Unable to create temp directory: {CONFIG.TEMP_DIR}")
        sys.exit(1)

    # TODO: We lock the bot down with oauth perms; can we shrink intents to match?
    intents = discord.Intents.default()
    intents.members = True

    guild = discord.Object(id=CONFIG.GUILD_ID)

    client = DiscordClient(
        intents=intents,
        upload=args.upload_commands,
        guild=guild,
    )
    tree = discord.app_commands.CommandTree(client)

    IronForgedCommands(tree, client)
    client.tree = tree

    client.run(CONFIG.BOT_TOKEN)
