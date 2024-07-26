import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401 # isort:skip
import argparse
import logging
import sys
from typing import Dict, Optional

import discord
from discord import app_commands

from ironforgedbot.client import DiscordClient
from ironforgedbot.commands.breakdown import breakdown
from ironforgedbot.commands.ingots.add_ingots import add_ingots
from ironforgedbot.commands.ingots.add_ingots_bulk import add_ingots_bulk
from ironforgedbot.commands.ingots.update_ingots import update_ingots
from ironforgedbot.commands.ingots.view_ingots import view_ingots
from ironforgedbot.commands.log.log_access import log_access
from ironforgedbot.commands.raffle.raffle_admin import raffle_admin
from ironforgedbot.commands.raffle.raffle_buy_tickets import raffle_buy_tickets
from ironforgedbot.commands.raffle.raffle_tickets import raffle_view_tickets
from ironforgedbot.commands.roster.roster import cmd_roster
from ironforgedbot.commands.score import score
from ironforgedbot.commands.sync_members import sync_members
from ironforgedbot.common.helpers import (
    validate_protected_request,
)
from ironforgedbot.common.responses import (
    send_error_response,
)
from ironforgedbot.common.roles import ROLES
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


class IronForgedCommands:
    def __init__(
        self,
        tree: discord.app_commands.CommandTree,
        discord_client: DiscordClient,
        # TODO: replace sheets client with a storage interface &
        # pass in a sheets impl.
        storage_client: IngotsStorage,
        tmp_dir_path: str,
    ):
        self._tree = tree
        self._discord_client = discord_client
        self._storage_client = storage_client
        self._tmp_dir_path = tmp_dir_path

        # Description only sets the brief description.
        # Arg descriptions are pulled from function definition.
        score_command = app_commands.Command(
            name="score",
            description="Compute your score, or the score of another member.",
            callback=self.score,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(score_command)

        breakdown_command = app_commands.Command(
            name="breakdown",
            description="View your score breakdown, or the breakdown of another member.",
            callback=self.breakdown,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(breakdown_command)

        ingots_command = app_commands.Command(
            name="ingots",
            description="View your ingot balance, or the balance of another member.",
            callback=self.ingots,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(ingots_command)

        addingots_command = app_commands.Command(
            name="addingots",
            description="Add or remove ingots to a player.",
            callback=self.addingots,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(addingots_command)

        addingotsbulk_command = app_commands.Command(
            name="addingotsbulk",
            description="Add or remove ingots to multiple players.",
            callback=self.addingotsbulk,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(addingotsbulk_command)

        updateingots_command = app_commands.Command(
            name="updateingots",
            description="Set a player's ingot count to a new value.",
            callback=self.updateingots,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(updateingots_command)

        raffleadmin_command = app_commands.Command(
            name="raffleadmin",
            description="Command wrapper for admin actions on raffles.",
            callback=self.raffleadmin,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(raffleadmin_command)

        raffletickets_command = app_commands.Command(
            name="raffletickets",
            description="View current raffle ticket count.",
            callback=self.raffletickets,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(raffletickets_command)

        buyraffletickets_command = app_commands.Command(
            name="buyraffletickets",
            description="Buy raffle tickets for 5000 ingots each.",
            callback=self.buyraffletickets,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(buyraffletickets_command)

        syncmembers_command = app_commands.Command(
            name="syncmembers",
            description="Sync members of Discord server with ingots storage.",
            callback=self.syncmembers,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(syncmembers_command)

        roster_command = app_commands.Command(
            name="roster",
            description="Builds an even roster from signups.",
            callback=self.roster,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(roster_command)

        log_command = app_commands.Command(
            name="logs",
            description="Allows access to bot logs.",
            callback=self.log_access,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(log_command)

    async def log_access(
        self, interaction: discord.Interaction, file_index: Optional[int]
    ):
        try:
            await log_access(interaction, file_index)
        except Exception as e:
            await interaction.response.defer()
            logger.error(e)
            await send_error_response(interaction, "Logs command encountered an error")

    async def roster(self, interaction: discord.Interaction, message_url: str):
        await interaction.response.defer()

        try:
            validate_protected_request(
                interaction, interaction.user.display_name, ROLES.LEADERSHIP
            )
        except (ReferenceError, ValueError) as error:
            logger.info(
                f"Member '{interaction.user.display_name}' tried using roster but does not have permission"
            )
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/roster message_url:{message_url}' on behalf of {interaction.user.display_name}"
        )

        await cmd_roster(
            interaction,
            message_url,
            self._discord_client.discord_guild,
            self._storage_client,
        )

    async def score(self, interaction: discord.Interaction, player: Optional[str]):
        try:
            await interaction.response.defer(thinking=True)
            await score(self, interaction, player)
        except Exception as e:
            logger.error(e)
            await send_error_response(interaction, "Score command encountered an error")

    async def breakdown(
        self, interaction: discord.Interaction, player: Optional[str] = None
    ):
        try:
            await interaction.response.defer(thinking=True)
            await breakdown(self, interaction, player)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Breakdown command encountered an error"
            )

    async def ingots(
        self, interaction: discord.Interaction, player: Optional[str] = None
    ):
        try:
            await interaction.response.defer(thinking=True)
            await view_ingots(self, interaction, player)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Ingots command encountered an error"
            )

    async def addingots(
        self,
        interaction: discord.Interaction,
        player: str,
        ingots: int,
        reason: str = "None",
    ):
        try:
            await interaction.response.defer(thinking=True)
            await add_ingots(self, interaction, player, ingots, reason)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Add ingots command encountered an error"
            )

    async def addingotsbulk(
        self,
        interaction: discord.Interaction,
        players: str,
        ingots: int,
        reason: str = "None",
    ):
        try:
            await interaction.response.defer(thinking=True)
            await add_ingots_bulk(self, interaction, players, ingots, reason)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Add ingots bulk command encountered an error"
            )

    async def updateingots(
        self,
        interaction: discord.Interaction,
        player: str,
        ingots: int,
        reason: str = "None",
    ):
        try:
            await interaction.response.defer(thinking=True)
            await update_ingots(self, interaction, player, ingots, reason)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Update ingots command encountered an error"
            )

    async def raffleadmin(self, interaction: discord.Interaction, subcommand: str):
        try:
            await interaction.response.defer(thinking=True)
            await raffle_admin(self, interaction, subcommand)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Raffle admin command encountered an error"
            )

    async def raffletickets(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
            await raffle_view_tickets(self, interaction)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "View raffle tickets command encountered an error"
            )

    async def buyraffletickets(self, interaction: discord.Interaction, tickets: int):
        try:
            await interaction.response.defer(thinking=True)
            await raffle_buy_tickets(self, interaction, tickets)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Buy raffle tickets command encountered an error"
            )

    async def syncmembers(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(thinking=True)
            await sync_members(self, interaction)
        except Exception as e:
            logger.error(e)
            await send_error_response(
                interaction, "Sync members command encountered an error"
            )


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
