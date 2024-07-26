from ironforgedbot.commands.ingots.add_ingots import add_ingots
from ironforgedbot.commands.ingots.add_ingots_bulk import add_ingots_bulk
from ironforgedbot.commands.ingots.update_ingots import update_ingots
import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401 # isort:skip

import argparse
import asyncio
import logging
import os
import random
import sys
from typing import Dict, Optional

import discord
from apscheduler.schedulers.background import BackgroundScheduler
from discord import app_commands
from reactionmenu import ViewButton, ViewMenu

from ironforgedbot.client import DiscordClient
from ironforgedbot.commands.breakdown import breakdown
from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.commands.hiscore.constants import (
    EMPTY_SPACE,
)
from ironforgedbot.commands.ingots.view_ingots import view_ingots
from ironforgedbot.commands.log.log_access import log_access
from ironforgedbot.commands.roster.roster import cmd_roster
from ironforgedbot.commands.score import score
from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_emoji,
    normalize_discord_string,
    validate_member_has_role,
    validate_playername,
    validate_protected_request,
    validate_user_request,
)
from ironforgedbot.common.ranks import (
    RANK_POINTS,
    RANKS,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
)
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS
from ironforgedbot.storage.sheets import SheetsStorage
from ironforgedbot.storage.types import IngotsStorage, Member, StorageError
from ironforgedbot.tasks.activity import check_activity, check_activity_reminder
from ironforgedbot.tasks.ranks import refresh_ranks

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
        """Parent command for doing admin actions around raffles.

        Args:
            subcommand: string of admin action to perform. Valid actions: [start_raffle, end_raffle, choose_winner].
                'start_raffle' will open purchasing of tickets, 'end_raffle' will close
                purchasing, and 'choose_winner' will choose a winner & display
                their winnings (alongside clearing storage for the next raffle).
        """

        await interaction.response.defer()

        try:
            validate_protected_request(
                interaction, interaction.user.display_name, ROLES.LEADERSHIP
            )
        except (ReferenceError, ValueError) as error:
            logger.info(
                f"Member '{interaction.user.display_name}' tried raffleadmin but does not have permission"
            )
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/raffleadmin {subcommand}' on behalf of "
            f"{normalize_discord_string(interaction.user.display_name).lower()}"
        )
        if subcommand.lower() == "start_raffle":
            await self._start_raffle(interaction)
        elif subcommand.lower() == "end_raffle":
            await self._end_raffle(interaction)
        elif subcommand.lower() == "choose_winner":
            await self._choose_winner(interaction)
        else:
            await interaction.followup.send("provided subcommand is not implemented")

    async def _start_raffle(self, interaction: discord.Interaction):
        """Starts a raffle, enabling purchase of raffle tickets.

        Expects provided interaction to have already deferred the response.
        """
        try:
            self._storage_client.start_raffle(
                normalize_discord_string(interaction.user.display_name).lower()
            )
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error starting raffle: {error}"
            )
            return

        await interaction.followup.send(
            "Started raffle! Members can now use ingots to purchase tickets."
        )

    async def _end_raffle(self, interaction: discord.Interaction):
        """Ends raffle, disabling purchase of tickets.

        Expects provided interaction to have already deferred the response.
        """
        try:
            self._storage_client.end_raffle(
                normalize_discord_string(interaction.user.display_name).lower()
            )
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error ending raffle: {error}"
            )
            return

        await interaction.followup.send(
            "Raffle ended! Members can no longer purchase tickets."
        )

    async def _choose_winner(self, interaction: discord.Interaction):
        """Chooses a winner & winning amount. Clears storage of all tickets."""
        try:
            current_tickets = self._storage_client.read_raffle_tickets()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error ending raffle: {error}"
            )
            return

        try:
            members = self._storage_client.read_members()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading current members: {error}"
            )
            return

        # Now we have ID:tickets & RSN:ID
        # Morph these into a List[RSN], where RSN appears once for each ticket
        # First, make our list of members a dictionary for faster lookups
        id_to_runescape_name = {}
        for member in members:
            id_to_runescape_name[member.id] = member.runescape_name

        entries = []
        for id, ticket_count in current_tickets.items():
            # Account for users who left clan since buying tickets.
            if id_to_runescape_name.get(id) is not None:
                entries.extend([id_to_runescape_name.get(id)] * ticket_count)

        winner = entries[random.randrange(0, len(entries))]

        winnings = len(entries) * 2500

        # TODO: Make this more fun by adding an entries file or rendering a graphic
        await interaction.followup.send(
            f"{winner} has won {winnings} ingots out of {len(entries)} entries!"
        )

        try:
            self._storage_client.delete_raffle_tickets(
                normalize_discord_string(interaction.user.display_name).lower()
            )
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error clearing ticket storage: {error}"
            )
            return

    async def raffletickets(self, interaction: discord.Interaction):
        """View calling user's current raffle ticket count."""

        await interaction.response.defer(thinking=True)

        try:
            _, caller = validate_user_request(
                interaction, interaction.user.display_name
            )
        except (ReferenceError, ValueError) as error:
            await send_error_response(interaction, str(error))
            return

        logger.info(f"Handling '/raffletickets' on behalf of {caller}")

        try:
            member = self._storage_client.read_member(caller)
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading member from storage: {error}"
            )
            return

        if member is None:
            await send_error_response(
                interaction,
                f"{caller} not found in storage, please reach out to leadership.",
            )
            return

        try:
            current_tickets = self._storage_client.read_raffle_tickets()
        except StorageError as error:
            await send_error_response(
                interaction,
                f"Encountered error reading raffle tickets from storage: {error}",
            )
            return

        count = 0
        for id, tickets in current_tickets.items():
            if id == member.id:
                count = tickets
                break

        await interaction.followup.send(f"{caller} has {count} tickets!")

    async def buyraffletickets(self, interaction: discord.Interaction, tickets: int):
        """Use ingots to buy tickets. Tickets cost 5000 ingots each."""
        await interaction.response.defer()

        try:
            _, caller = validate_user_request(
                interaction, interaction.user.display_name
            )
        except (ReferenceError, ValueError) as error:
            await send_error_response(interaction, str(error))
            return

        logger.info(f"Handling '/buyraffletickets {tickets}' on behalf of {caller}")

        try:
            ongoing_raffle = self._storage_client.read_raffle()
        except StorageError as error:
            await send_error_response(
                interaction,
                f"Encountered error reading raffle status from storage: {error}",
            )
            return

        if not ongoing_raffle:
            await send_error_response(
                interaction,
                "FAILED_PRECONDITION: There is no ongoing raffle; tickets cannot be bought.",
            )
            return

        # First, read member to get Discord ID & ingot count
        try:
            member = self._storage_client.read_member(caller)
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading member from storage: {error}"
            )
            return

        if member is None:
            await send_error_response(
                interaction,
                f"{caller} not found in storage, please reach out to leadership.",
            )
            return

        # Now we have the Discord ID & current ingot count
        # Does the user have enough ingots to make the purchase?
        cost = tickets * 5000
        if cost > member.ingots:
            await interaction.followup.send(
                f"{caller} does not have enough ingots for {tickets} tickets.\n"
                + f"Cost: {cost}, current ingots: {member.ingots}"
            )
            return

        # We got this for, do the transactions
        member.ingots -= cost
        try:
            self._storage_client.update_members(
                [member], caller, note="Bought raffle tickets"
            )
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error updating member ingot count: {error}"
            )
            return

        try:
            self._storage_client.add_raffle_tickets(member.id, tickets)
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error adding raffle tickets: {error}"
            )

            return

        await interaction.followup.send(
            f"{caller} successfully bought {tickets} tickets for {cost} ingots!"
        )

    async def syncmembers(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            _, caller = validate_protected_request(
                interaction, interaction.user.display_name, ROLES.LEADERSHIP
            )
        except (ReferenceError, ValueError) as error:
            logger.info(
                f"Member '{interaction.user.display_name}' tried syncmembers but does not have permission"
            )
            await send_error_response(interaction, str(error))
            return

        output = ""
        logger.info(f"Handling '/syncmembers' on behalf of {caller}")

        # Perform a cross join between current Discord members and
        # entries in the sheet.
        # First, read all members from Discord.
        members = []
        member_ids = []

        assert interaction.guild is not None
        for member in interaction.guild.members:
            if validate_member_has_role(member, ROLES.MEMBER):
                members.append(member)
                member_ids.append(member.id)

        # Then, get all current entries from storage.
        try:
            existing = self._storage_client.read_members()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading members: {error}"
            )
            return

        written_ids = [member.id for member in existing]

        # Now for the actual diffing.
        # First, what new members are in Discord but not the sheet?
        new_members = []
        for member in members:
            if member.id not in written_ids:
                # Don't allow users without a nickname into storage.
                if not member.nick or len(member.nick) < 1:
                    output += f"skipped user {member.name} because they don't have a nickname in Discord\n"
                    continue
                new_members.append(
                    Member(
                        id=int(member.id),
                        runescape_name=normalize_discord_string(member.nick).lower(),
                        ingots=0,
                    )
                )
                output += f"added user {normalize_discord_string(member.nick).lower()} because they joined\n"

        try:
            self._storage_client.add_members(new_members, "User Joined Server")
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error writing new members: {e}"
            )
            return

        # Okay, now for all the users who have left.
        leaving_members = []
        for existing_member in existing:
            if existing_member.id not in member_ids:
                leaving_members.append(existing_member)
                output += f"removed user {existing_member.runescape_name} because they left the server\n"
        try:
            self._storage_client.remove_members(leaving_members, "User Left Server")
        except StorageError as e:
            await interaction.followup.send(f"Encountered error removing members: {e}")
            return

        # Update all users that have changed their RSN.
        changed_members = []
        for member in members:
            for existing_member in existing:
                if member.id == existing_member.id:
                    # If a member is already in storage but had their nickname
                    # unset, set rsn to their Discord name.
                    # Otherwise, sorting fails when comparing NoneType.
                    if member.nick is None:
                        if member.name != existing_member.runescape_name:
                            changed_members.append(
                                Member(
                                    id=existing_member.id,
                                    runescape_name=member.name.lower(),
                                    ingots=existing_member.ingots,
                                )
                            )
                    else:
                        if (
                            normalize_discord_string(member.nick).lower()
                            != existing_member.runescape_name
                        ):
                            changed_members.append(
                                Member(
                                    id=existing_member.id,
                                    runescape_name=normalize_discord_string(
                                        member.nick
                                    ).lower(),
                                    ingots=existing_member.ingots,
                                )
                            )

        for changed_member in changed_members:
            output += f"updated RSN for {changed_member.runescape_name}\n"

        try:
            self._storage_client.update_members(changed_members, "Name Change")
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error updating changed members: {e}"
            )
            return

        path = os.path.join(self._tmp_dir_path, f"syncmembers_{caller}.txt")
        with open(path, "w") as f:
            f.write(output)

        with open(path, "rb") as f:
            discord_file = discord.File(f, filename="syncmembers.txt")
            await interaction.followup.send(
                "Successfully synced ingots storage with current members!",
                file=discord_file,
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
