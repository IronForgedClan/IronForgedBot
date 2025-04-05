import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401 # isort:skip
import argparse
import logging
import os
import sys

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.command_tree import IronForgedCommands, IronForgedCommandTree
from ironforgedbot.config import CONFIG
from ironforgedbot.http import HTTP
from ironforgedbot.state import STATE
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS
from ironforgedbot.storage.sheets import SHEETS

logger = logging.getLogger(__name__)


def init_bot():
    if CONFIG and SHEETS and STATE and HTTP and BOSSES and CLUES and RAIDS and SKILLS:
        logger.info("Requirements loaded")

    create_temp_dir(CONFIG.TEMP_DIR)

    args = parse_cli_arguments()
    intents = create_discord_intents()
    client = create_client(intents, args.upload, CONFIG.GUILD_ID)

    logger.info(f"Starting Iron Forged Bot v{CONFIG.BOT_VERSION}")
    client.run(CONFIG.BOT_TOKEN)


def parse_cli_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A discord bot for the Iron Forged Old School RuneScape clan."
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        default=False,
        help="Uploads commands to discord server.",
    )

    return parser.parse_args()


def create_temp_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        logging.critical(f"Unable to create temp directory: {path}")
        sys.exit(1)


def create_discord_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.members = True

    return intents


def create_client(
    intents: discord.Intents, upload: bool, guild_id: int
) -> discord.Client:
    guild = discord.Object(id=guild_id)

    client = DiscordClient(
        intents=intents,
        upload=upload,
        guild=guild,
    )
    tree = IronForgedCommandTree(client)

    IronForgedCommands(tree, client)
    client.tree = tree

    return client


if __name__ == "__main__":
    init_bot()
