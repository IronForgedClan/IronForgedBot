import argparse
import asyncio
import logging
import os
import random
import sys
from typing import Dict

import discord
from apscheduler.schedulers.background import BackgroundScheduler
from discord import app_commands

from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.commands.hiscore.constants import (
    CLUE_DISPLAY_ORDER,
    RAIDS_DISPLAY_ORDER,
    SKILLS_DISPLAY_ORDER,
    BOSS_DISPLAY_ORDER,
)
from ironforgedbot.common.helpers import (
    normalize_discord_string,
    calculate_percentage,
    find_emoji,
)
from ironforgedbot.common.player import validate_player
from ironforgedbot.common.responses import (
    build_error_message_string,
    build_response_embed,
    send_error_response,
)
from ironforgedbot.common.ranks import (
    RANKS,
    RANK_POINTS,
    get_next_rank_from_points,
    get_rank_from_points,
    get_rank_color_from_points,
)
from ironforgedbot.storage.sheets import SheetsStorage
from ironforgedbot.storage.types import IngotsStorage, Member, StorageError
from ironforgedbot.tasks.ranks import refresh_ranks

from reactionmenu import ViewMenu, ViewButton


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
        logging.error("validation failed; SHEETID required but not present in env")
        return False
    if config.get("GUILDID") is None:
        logging.error("validation failed; GUILDID required but not present in env")
        return False
    if config.get("BOT_TOKEN") is None:
        logging.error("validation failed; BOT_TOKEN required but not present in env")
        return False

    return True


def check_role(member: discord.Member, checked_role: str) -> bool:
    """Check if a member has a given role."""
    roles = member.roles
    for role in roles:
        if role.name == checked_role:
            return True

    return False


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
    ):
        super().__init__(intents=intents)
        self.upload = upload
        self.guild = guild
        self.ranks_update_channel = ranks_update_channel

    @property
    def tree(self):
        return self._tree

    @tree.setter
    def tree(self, value: app_commands.CommandTree):
        self._tree = value

    async def setup_hook(self):
        # Copy commands to the guild (Discord server)
        # TODO: Move this to a separate CLI solely for uploading commands.
        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

        # Starting background jobs
        loop = asyncio.get_running_loop()

        discord_guild = self.get_guild(guild.id)
        scheduler = BackgroundScheduler()
        # Use 'interval' with minutes | seconds = x for testing
        scheduler.add_job(
            refresh_ranks,
            "cron",
            args=[discord_guild, self.ranks_update_channel, loop],
            hour=2,
            minute=0,
            second=0,
            timezone="UTC",
        )
        scheduler.start()

        print("Workers started")
        print("------")


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
            description="Compute clan score for a player.",
            callback=self.score,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(score_command)

        breakdown_command = app_commands.Command(
            name="breakdown",
            description="Get full breakdown of score for a player.",
            callback=self.breakdown,
            nsfw=False,
            parent=None,
            auto_locale_strings=True,
        )
        self._tree.add_command(breakdown_command)

        ingots_command = app_commands.Command(
            name="ingots",
            description="View current ingots for a player.",
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

    async def score(self, interaction: discord.Interaction, player: str):
        """Compute clan score for a Runescape player name.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Runescape playername to look up score for.
        """
        if not interaction.guild:
            await send_error_response(interaction, "Error accessing guild")
            return

        member = validate_player(interaction.guild, player)
        if not member:
            await send_error_response(interaction, f"Player '{player}' is not a member of this server")
            return

        player_name = member.display_name

        logging.info(
            (
                f"Handling '/score player:{player_name}' on behalf of "
                f"{normalize_discord_string(interaction.user.display_name)}"
            )
        )
        await interaction.response.defer()

        try:
            skill_info, points_by_activity = score_info(player_name)
        except RuntimeError as e:
            await interaction.followup.send(build_error_message_string(str(e)))
            return

        skill_points = 0
        for _, skill in skill_info.items():
            skill_points += skill["points"]

        activity_points = 0
        for _, v in points_by_activity.items():
            activity_points += v["points"]

        points_total = skill_points + activity_points
        rank_name = get_rank_from_points(points_total)
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(self._discord_client.emojis, rank_name)

        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()].value
        next_rank_icon = find_emoji(self._discord_client.emojis, next_rank_name)

        embed = build_response_embed(f"{rank_icon} {member.display_name}", "", rank_color)
        embed.add_field(
            name="Skill Points",
            value=f"{skill_points:,} ({calculate_percentage(skill_points, points_total)}%)",
            inline=True,
        )
        embed.add_field(
            name="Activity Points",
            value=f"{activity_points:,} ({calculate_percentage(activity_points, points_total)}%)",
            inline=True,
        )
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
        embed.add_field(name="Rank", value=f"{rank_icon} {rank_name}", inline=True)

        if rank_name == RANKS.MYTH.value:
            grass_emoji = find_emoji(self._discord_client.emojis, "grass")
            embed.add_field(
                name="",
                value=(
                    f"{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}"
                    f"{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}{grass_emoji}"
                ),
                inline=False,
            )
        else:
            embed.add_field(name="", value="", inline=False)
            embed.add_field(
                name="Rank Progress",
                value=(
                    f"{rank_icon} -> {next_rank_icon} {points_total}/{next_rank_point_threshold} "
                    f"({calculate_percentage(points_total, next_rank_point_threshold)}%)"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    async def breakdown(self, interaction: discord.Interaction, player: str):
        """Compute player score with complete source enumeration.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Runescape username to break down clan score for.
        """
        if not interaction.guild:
            await send_error_response(interaction, "Error accessing guild")
            return

        member = validate_player(interaction.guild, player)
        if not member:
            await send_error_response(interaction, f"Player '{player}' is not a member of this server")
            return

        player = member.display_name

        logging.info(
            f"Handling '/breakdown player:{player}' on behalf of "
            f"{normalize_discord_string(interaction.user.display_name)}"
        )
        await interaction.response.defer()

        try:
            skills_info, activities_info = score_info(player)
        except RuntimeError as e:
            await interaction.followup.send(str(e))
            return

        skill_points = 0
        for _, skill in skills_info.items():
            skill_points += skill["points"]

        activity_points = 0
        for _, activity in activities_info.items():
            activity_points += activity["points"]

        points_total = skill_points + activity_points
        rank_name = get_rank_from_points(points_total)
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(self._discord_client.emojis, rank_name)

        rank_breakdown_embed = build_response_embed(
            f"{rank_icon} {player} - Rank Ladder",
            "A visual representation of the ranking ladder,\nincluding point thresholds.",
            rank_color,
        )

        for rank in RANKS:
            icon = find_emoji(self._discord_client.emojis, rank)
            rank_point_threshold = RANK_POINTS[rank.upper()].value
            rank_breakdown_embed.add_field(
                name=(
                    f"{icon} {rank}%s"
                    % ("⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀<-- _You are here_" if rank == rank_name else "")
                ),
                value=f"⠀⠀{rank_point_threshold:,}+ points",
                inline=False,
            )

        if rank_name != RANKS.MYTH.value:
            next_rank_name = get_next_rank_from_points(points_total)
            next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()].value
            next_rank_icon = find_emoji(self._discord_client.emojis, next_rank_name)
            rank_breakdown_embed.add_field(
                name="Your Progress",
                value=(
                    f"{rank_icon} -> {next_rank_icon} {points_total:,}/{next_rank_point_threshold:,} "
                    f"({calculate_percentage(points_total, next_rank_point_threshold)}%)"
                ),
                inline=False,
            )

        skill_breakdown_embed = build_response_embed(
            f"{rank_icon} {player}'s Skilling Points",
            f"**{skill_points:,}** points awarded for skill xp.",
            rank_color,
        )

        for skill in SKILLS_DISPLAY_ORDER:
            skill_icon = find_emoji(self._discord_client.emojis, skill.lower())
            skill_breakdown_embed.add_field(
                name=f"{skill_icon} {skills_info[skill]['points']:,} points",
                value=f"⠀⠀{skills_info[skill]['xp']:,} xp",
                inline=True,
            )

        skill_breakdown_embed.add_field(
            name=f"{rank_icon} Skill Total",
            value=f"⠀⠀**{points_total:,} points**",
            inline=True,
        )

        # There is a 25 field limit on embeds, so we need to paginate.
        # As not every player has kc on every boss we don't need to show
        # all bosses, so this won't be as bad for some players.
        field_count = 0
        boss_embeds = []

        working_embed = build_response_embed(
            f"{rank_icon} {player} - Bossing",
            "Points awarded for boss kill count.",
            rank_color,
        )

        for boss_type, display_name in BOSS_DISPLAY_ORDER.items():
            if field_count == 24:
                field_count = 0
                boss_embeds.append((working_embed))
                working_embed = build_response_embed(
                    f"{rank_icon} {player} - Bossing (Part {boss_embeds.__len__() + 1})",
                    "Points awarded for boss kill count.",
                    rank_color,
                )

            boss_info = activities_info.get(boss_type)
            if boss_info is None:
                continue

            field_count += 1
            boss_icon = find_emoji(self._discord_client.emojis, display_name)
            working_embed.add_field(
                name=f"{boss_icon} {boss_info['points']:,} points",
                value=f"⠀⠀{boss_info['kc']:,} kc",
            )

        boss_embeds.append(working_embed)

        raid_breakdown_embed = build_response_embed(
            f"{rank_icon} {player} - Raids",
            "Points awarded for raid completions.",
            rank_color,
        )

        for raid_type, display_name in RAIDS_DISPLAY_ORDER.items():
            raid_info = activities_info.get(raid_type)
            if raid_info is None:
                raid_info = {"points": 0, "kc": 0}
            raid_icon = find_emoji(self._discord_client.emojis, display_name)
            raid_breakdown_embed.add_field(
                name=f"{raid_icon} {raid_info['points']:,} points",
                value=f"⠀⠀{raid_info['kc']:,} kc",
            )

        clue_breakdown_embed = build_response_embed(
            f"{rank_icon} {player} - Cluescrolls",
            "Points awarded for cluescroll completions.",
            rank_color,
        )

        clue_icon = find_emoji(self._discord_client.emojis, "cluescroll")
        for clue_type, display_name in CLUE_DISPLAY_ORDER.items():
            clue_info = activities_info.get(clue_type)
            if clue_info is None:
                clue_info = {"points": 0, "kc": 0}
            clue_breakdown_embed.add_field(
                name=f"{clue_icon} {clue_info['points']:,} points",
                value=f"⠀⠀{clue_info['kc']:,} {display_name.lower()}",
            )

        menu = ViewMenu(
            interaction,
            menu_type=ViewMenu.TypeEmbed,
            show_page_director=True,
            timeout=600,
            delete_on_timeout=True,
        )

        menu.add_page(skill_breakdown_embed)
        for embed in boss_embeds:
            menu.add_page(embed)
        menu.add_page(raid_breakdown_embed)
        menu.add_page(clue_breakdown_embed)
        menu.add_page(rank_breakdown_embed)

        menu.add_button(ViewButton.back())
        menu.add_button(ViewButton.next())

        await menu.start()

    async def ingots(self, interaction: discord.Interaction, player: str):
        """View ingots for a Runescape playername.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Runescape username to view ingot count for.
        """
        if not validate_player_name(player):
            await interaction.response.send_message(
                "FAILED_PRECONDITION: RSNs can only be 12 characters long."
            )
            return

        logging.info(
            f"Handling '/ingots player:{player}' on behalf of {normalize_discord_string(interaction.user.display_name)}"
        )
        await interaction.response.defer()

        # Strip whitespaces from mis-typing.
        player = player.strip()
        try:
            member = self._storage_client.read_member(player.lower())
        except StorageError as e:
            await interaction.followup.send(f"Encountered error reading member: {e}")
            return

        if member is None:
            await interaction.followup.send(f"{player} not found in storage")
            return

        ingot_icon = find_emoji(self._discord_client.emojis, "Ingot")
        await interaction.followup.send(
            f"{player} has {member.ingots:,} ingots {ingot_icon}"
        )

    async def addingots(
        self,
        interaction: discord.Interaction,
        player: str,
        ingots: int,
        reason: str = "None",
    ):
        """Add ingots to a Runescape alias.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Runescape username to add ingots to.
            ingots: number of ingots to add to this player.
        """
        # interaction.user can be a User or Member, but we can only
        # rely on permission checking for a Member.
        caller = interaction.user
        if isinstance(caller, discord.User):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {caller.name} is not in this guild."
            )
            return

        if not check_role(caller, "Leadership"):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {caller.name} is not in a leadership role."
            )
            return

        if not validate_player_name(player):
            await interaction.response.send_message(
                "FAILED_PRECONDITION: RSNs can only be 12 characters long."
            )
            return

        if caller.nick is None:
            await interaction.response.send_message(
                "FAILED_PRECONDITION: caller does not have a nickname set."
            )
            return

        caller = normalize_discord_string(caller.nick).lower()
        logging.info(
            f"Handling '/addingots player:{player} ingots:{ingots} reason:{reason}' on behalf of {caller}"
        )
        await interaction.response.defer()

        player = player.strip()
        try:
            member = self._storage_client.read_member(player.lower())
        except StorageError as e:
            await interaction.followup.send(f"Encountered error reading member: {e}")
            return

        if member is None:
            await interaction.followup.send(f"{player} wasn't found.")
            return

        member.ingots += ingots

        try:
            self._storage_client.update_members([member], caller, note=reason)
        except StorageError as e:
            await interaction.followup.send(f"Encountered error writing ingots: {e}")
            return

        ingot_icon = find_emoji(self._discord_client.emojis, "Ingot")
        await interaction.followup.send(
            f"Added {ingots:,} ingots to {player}; reason: {reason}. They now have {member.ingots:,} ingots {ingot_icon}"
        )

    async def addingotsbulk(
        self,
        interaction: discord.Interaction,
        players: str,
        ingots: int,
        reason: str = "None",
    ):
        """Add ingots to a Runescape alias.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Comma-separated list of Runescape usernames to add ingots to.
            ingots: number of ingots to add to this player.
        """
        # interaction.user can be a User or Member, but we can only
        # rely on permission checking for a Member.
        caller = interaction.user
        if isinstance(caller, discord.User):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {caller.name} is not in this guild."
            )
            return

        if not check_role(caller, "Leadership"):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {caller.name} is not in a leadership role."
            )
            return

        if caller.nick is None:
            await interaction.response.send_message(
                "FAILED_PRECONDITION: caller does not have a nickname set."
            )
            return

        caller = normalize_discord_string(caller.nick).lower()
        logging.info(
            f"Handling '/addingotsbulk players:{players} ingots:{ingots} reason:{reason}' on behalf of {caller}"
        )
        await interaction.response.defer()

        player_names = players.split(",")
        player_names = [player.strip() for player in player_names]
        for player in player_names:
            if not validate_player_name(player):
                await interaction.followup.send(
                    f"FAILED_PRECONDITION: {player} is longer than 12 characters."
                )
                return

        try:
            members = self._storage_client.read_members()
        except StorageError as e:
            await interaction.followup.send(f"Encountered error reading member: {e}")
            return

        output = []
        members_to_update = []
        for player in player_names:
            found = False
            for member in members:
                if member.runescape_name == player.lower():
                    found = True
                    member.ingots += ingots
                    members_to_update.append(member)
                    output.append(
                        f"Added {ingots:,} ingots to {player}. They now have {member.ingots:,} ingots"
                    )
                    break
            if not found:
                output.append(f"{player} not found in storage.")

        try:
            self._storage_client.update_members(members_to_update, caller, note=reason)
        except StorageError as e:
            await interaction.followup.send(f"Encountered error writing ingots: {e}")
            return

        # Our output can be larger than the interaction followup max.
        # Send it in a file to accomodate this.
        path = os.path.join(self._tmp_dir_path, f"addingotsbulk_{caller}.txt")
        with open(path, "w") as f:
            f.write("\n".join(output))

        with open(path, "rb") as f:
            discord_file = discord.File(f, filename="addingotsbulk.txt")
            await interaction.followup.send(
                f"Added ingots to multiple members! Reason: {reason}", file=discord_file
            )

    async def updateingots(
        self,
        interaction: discord.Interaction,
        player: str,
        ingots: int,
        reason: str = "None",
    ):
        """Set ingots for a Runescape alias.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Runescape username to view ingot count for.
            ingots: New ingot count for this user.
        """
        # interaction.user can be a User or Member, but we can only
        # rely on permission checking for a Member.
        caller = interaction.user
        if isinstance(caller, discord.User):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {caller.name} is not in this guild."
            )
            return

        if not check_role(caller, "Leadership"):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {caller.name} is not in a leadership role."
            )
            return

        if not validate_player_name(player):
            await interaction.response.send_message(
                "FAILED_PRECONDITION: RSNs can only be 12 characters long."
            )
            return

        if caller.nick is None:
            await interaction.response.send_message(
                "FAILED_PRECONDITION: caller does not have a nickname set."
            )
            return

        caller = normalize_discord_string(caller.nick).lower()
        logging.info(
            f"Handling '/updateingots player:{player} ingots:{ingots} reason:{reason}' on behalf of {caller}"
        )

        await interaction.response.defer()

        player = player.strip()
        try:
            member = self._storage_client.read_member(player.lower())
        except StorageError as e:
            await interaction.followup.send(f"Encountered error reading member: {e}")
            return

        if member is None:
            await interaction.followup.send(f"{player} wasn't found.")
            return

        member.ingots = ingots

        try:
            self._storage_client.update_members([member], caller, note=reason)
        except StorageError as e:
            await interaction.followup.send(f"Encountered error writing ingots: {e}")
            return

        ingot_icon = find_emoji(self._discord_client.emojis, "Ingot")
        await interaction.followup.send(
            f"Set ingot count to {ingots:,} for {player}. Reason: {reason} {ingot_icon}"
        )

    async def raffleadmin(self, interaction: discord.Interaction, subcommand: str):
        """Parent command for doing admin actions around raffles.

        Args:
            subcommand: string of admin action to perform. Valid actions: [start_raffle, end_raffle, choose_winner].
                'start_raffle' will open purchasing of tickets, 'end_raffle' will close
                purchasing, and 'choose_winner' will choose a winner & display
                their winnings (alongside clearing storage for the next raffle).
        """
        if interaction.user.display_name is None:
            await interaction.response.send_message(
                "FAILED_PRECONDITION: caller does not have a nickname set."
            )
            return

        logging.info(
            f"Handling '/raffleadmin {subcommand}' on behalf of "
            f"{normalize_discord_string(interaction.user.display_name).lower()}"
        )
        await interaction.response.defer()

        # interaction.user can be a User or Member, but we can only
        # rely on permission checking for a Member.
        caller = interaction.user
        if isinstance(caller, discord.User):
            await interaction.followup.send(
                f"PERMISSION_DENIED: {caller.name} is not in this guild."
            )
            return

        if not check_role(caller, "Leadership"):
            await interaction.followup.send(
                f"PERMISSION_DENIED: {caller.name} is not in a leadership role."
            )
            return

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
        except StorageError as e:
            await interaction.followup.send(f"Encountered error starting raffle: {e}")
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
        except StorageError as e:
            await interaction.followup.send(f"Encountered error ending raffle: {e}")
            return

        await interaction.followup.send(
            "Raffle ended! Members can no longer purchase tickets."
        )

    async def _choose_winner(self, interaction: discord.Interaction):
        """Chooses a winner & winning amount. Clears storage of all tickets."""
        try:
            current_tickets = self._storage_client.read_raffle_tickets()
        except StorageError as e:
            await interaction.followup.send(f"Encountered error reading tickets: {e}")
            return

        try:
            members = self._storage_client.read_members()
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error reading current members: {e}"
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
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error clearing ticket storage: {e}"
            )
            return

    async def raffletickets(self, interaction: discord.Interaction):
        """View calling user's current raffle ticket count."""
        await interaction.response.defer()

        # interaction.user can be a User or Member, but we can only
        # rely on permission checking for a Member.
        caller = interaction.user
        if isinstance(caller, discord.User):
            await interaction.followup.send(
                f"PERMISSION_DENIED: {caller.name} is not in this guild."
            )
            return

        if caller.nick is None:
            await interaction.followup.send(
                f"FAILED_PRECONDITION: {caller.name} does not have a nickname set."
            )
            return

        caller = normalize_discord_string(caller.nick).lower()
        logging.info(f"Handling '/raffletickets' on behalf of {caller}")

        try:
            member = self._storage_client.read_member(caller)
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error reading member from storage: {e}"
            )
            return

        if member is None:
            await interaction.followup.send(
                f"{caller} not found in storage, please reach out to leadership."
            )
            return

        try:
            current_tickets = self._storage_client.read_raffle_tickets()
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error reading raffle tickets from storage: {e}"
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

        # interaction.user can be a User or Member, but we can only
        # rely on permission checking for a Member.
        caller = interaction.user
        if isinstance(caller, discord.User):
            await interaction.followup.send(
                f"PERMISSION_DENIED: {caller.name} is not in this guild."
            )
            return

        if caller.nick is None:
            await interaction.followup.send(
                f"FAILED_PRECONDITION: {caller.name} does not have a nickname set."
            )
            return

        caller = normalize_discord_string(caller.nick).lower()
        logging.info(f"Handling '/buyraffletickets {tickets}' on behalf of {caller}")

        try:
            ongoing_raffle = self._storage_client.read_raffle()
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error reading raffle status from storage: {e}"
            )
            return

        if not ongoing_raffle:
            await interaction.followup.send(
                "FAILED_PRECONDITION: There is no ongoing raffle; tickets cannot be bought."
            )
            return

        # First, read member to get Discord ID & ingot count
        try:
            member = self._storage_client.read_member(caller)
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error reading member from storage: {e}"
            )
            return

        if member is None:
            await interaction.followup.send(
                f"{caller} not found in storage, please reach out to leadership."
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
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error updating member ingot count: {e}"
            )
            return

        try:
            self._storage_client.add_raffle_tickets(member.id, tickets)
        except StorageError as e:
            await interaction.followup.send(
                f"Encountered error adding raffle tickets: {e}"
            )
            return

        await interaction.followup.send(
            f"{caller} successfully bought {tickets} tickets for {cost} ingots!"
        )

    async def syncmembers(self, interaction: discord.Interaction):
        output = ""
        mutator = interaction.user
        if isinstance(mutator, discord.User):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {mutator.name} is not in this guild."
            )
            return

        if not check_role(mutator, "Leadership"):
            await interaction.response.send_message(
                f"PERMISSION_DENIED: {mutator.name} is not in a leadership role."
            )
            return

        if mutator.nick is None:
            await interaction.response.send_message(
                "FAILED_PRECONDITION: caller does not have a nickname set."
            )
            return

        caller = normalize_discord_string(mutator.nick).lower()
        logging.info(f"Handling '/syncmembers' on behalf of {caller}")

        await interaction.response.defer()
        # Perform a cross join between current Discord members and
        # entries in the sheet.
        # First, read all members from Discord.
        members = []
        member_ids = []
        for member in self._discord_client.get_guild(
            self._discord_client.guild.id
        ).members:
            if check_role(member, "Member"):
                members.append(member)
                member_ids.append(member.id)

        # Then, get all current entries from storage.
        try:
            existing = self._storage_client.read_members()
        except StorageError as e:
            await interaction.followup.send(f"Encountered error reading members: {e}")
            return

        original_length = len(existing)
        written_ids = [member.id for member in existing]

        # Now for the actual diffing.
        # First, what new members are in Discord but not the sheet?
        new_members = []
        for member in members:
            if member.id not in written_ids:
                # Don't allow users without a nickname into storage.
                if member.nick is None:
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
    parser.add_argument(
        "--logfile",
        default="./ironforgedbot.log",
        required=False,
        help="Path to file to write log entries to.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(message)s", filename=args.logfile, level=logging.INFO
    )

    # also log to stderr
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Fail out early if our required args are not present.
    init_config = read_dotenv(args.dotenv_path)
    if not validate_initial_config(init_config):
        sys.exit(1)

    # TODO: We lock the bot down with oauth perms; can we shrink intents to match?
    intents = discord.Intents.default()
    intents.members = True
    guild = discord.Object(id=init_config.get("GUILDID"))
    client = DiscordClient(
        intents=intents,
        upload=args.upload_commands,
        guild=guild,
        ranks_update_channel=init_config.get("RANKS_UPDATE_CHANNEL"),
    )
    tree = discord.app_commands.CommandTree(client)

    storage_client = SheetsStorage.from_account_file(
        "service.json", init_config.get("SHEETID")
    )

    commands = IronForgedCommands(tree, client, storage_client, args.tmp_dir)
    client.tree = tree

    client.run(init_config.get("BOT_TOKEN"))
