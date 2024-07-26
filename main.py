import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401 # isort:skip
import argparse
import logging
import sys
from typing import Dict

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS
from ironforgedbot.storage.sheets import SheetsStorage
from ironforgedbot.storage.types import IngotsStorage

logger = logging.getLogger(__name__)


def read_dotenv(path: str) -> Dict[str, str]:
    """Read config from a file of k=v entries."""
    config = {}
    with open(path, "r") as f:
        for line in f:
            tmp = line.partition("=")
            config[tmp[0]] = tmp[2].removesuffix("\n")

    return config


def validate_initial_config(config: Dict[str, str]) -> bool:
    if config.get("SHEETID") is None:
        logger.error("validation failed; SHEETID required but not present in env")
        return False
    if config.get("GUILDID") is None:
        logger.error("validation failed; GUILDID required but not present in env")
        return False
    if config.get("BOT_TOKEN") is None:
        logger.error("validation failed; BOT_TOKEN required but not present in env")
        return False

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A discord bot for Iron Forged.")
    parser.add_argument(
        "--dotenv_path",
        default="./.env",
        required=False,
        help="Filepath for .env with startup k/v pairs.",
    )
    parser.add_argument(
        "--upload_commands",
        action="store_true",
        help="If supplied, will upload commands to discord server.",
    )
    parser.add_argument(
        "--tmp_dir",
        default="./commands_tmp",
        required=False,
        help="Directory path for where to store point break downs to upload to discord.",
    )

    args = parser.parse_args()

    # Fail out early if our required args are not present.
    init_config = read_dotenv(args.dotenv_path)
    if not validate_initial_config(init_config):
        sys.exit(1)

    # Fail out if any errors reading local config data
    try:
        if BOSSES is None or len(BOSSES) < 1:
            raise Exception("Error loading boss data")
        if CLUES is None or len(CLUES) < 1:
            raise Exception("Error loading clue data")
        if RAIDS is None or len(RAIDS) < 1:
            raise Exception("Error loading raid data")
        if SKILLS is None or len(SKILLS) < 1:
            raise Exception("Error loading skill data")
    except Exception as e:
        logger.critical(e)
        sys.exit(1)

    # TODO: We lock the bot down with oauth perms; can we shrink intents to match?
    intents = discord.Intents.default()
    intents.members = True
    guild = discord.Object(id=init_config.get("GUILDID"))

    storage_client: IngotsStorage = SheetsStorage.from_account_file(
        "service.json", init_config.get("SHEETID")
    )

    client = DiscordClient(
        intents=intents,
        upload=args.upload_commands,
        guild=guild,
        ranks_update_channel=init_config.get("RANKS_UPDATE_CHANNEL"),
        wom_api_key=init_config.get("WOM_API_KEY"),
        wom_group_id=int(init_config.get("WOM_GROUP_ID")),
        storage=storage_client,
    )
    tree = discord.app_commands.CommandTree(client)

    commands = IronForgedCommands(tree, client, storage_client, args.tmp_dir)
    client.tree = tree

    client.run(init_config.get("BOT_TOKEN"))
