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

import ironforgedbot.logging_config  # pyright: ignore  # noqa: F401
from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.commands.hiscore.constants import (
    EMPTY_SPACE,
)
from ironforgedbot.commands.log.log_access import cmd_log_access
from ironforgedbot.commands.roster.roster import cmd_roster
from ironforgedbot.commands.syncmembers.syncmembers import cmd_sync_members
from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_emoji,
    normalize_discord_string,
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
from ironforgedbot.storage.types import IngotsStorage, StorageError
from ironforgedbot.tasks.activity import job_check_activity, job_check_activity_reminder
from ironforgedbot.tasks.ranks import job_refresh_ranks
from ironforgedbot.tasks.sync import job_sync_members

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
    def tree(self, value: app_commands.CommandTree):
        self._tree = value

    async def setup_hook(self):
        # Copy commands to the guild (Discord server)
        # TODO: Move this to a separate CLI solely for uploading commands.
        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")

        # Starting background jobs
        loop = asyncio.get_running_loop()

        self.discord_guild = self.get_guild(guild.id)
        scheduler = BackgroundScheduler()

        # Use 'interval' with minutes | seconds = x for testing or next_run_time=datetime.now()
        # from datetime import datetime
        scheduler.add_job(
            job_refresh_ranks,
            "cron",
            args=[self.discord_guild, self.ranks_update_channel, loop],
            hour=2,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            job_check_activity_reminder,
            "cron",
            args=[self.discord_guild, self.ranks_update_channel, loop, self.storage],
            day_of_week="mon",
            hour=0,
            minute=0,
            second=0,
            timezone="UTC",
        )

        scheduler.add_job(
            job_check_activity,
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

        scheduler.add_job(
                job_sync_members,
                "cron",
                args=[self.discord_guild, self.ranks_update_channel, loop, self.storage],
                hour="*/3",
                minute=50,
                second=0,
                timezone="UTC",
        )

        scheduler.start()


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

    async def log_access(self, interaction: discord.Interaction, file_index: Optional[int]):
        await cmd_log_access(interaction, file_index)

    async def roster(self, interaction: discord.Interaction, message_url: str):
        await cmd_roster(interaction, message_url, self._discord_client.discord_guild, self._storage_client)

    async def score(self, interaction: discord.Interaction, player: Optional[str]):
        """Compute clan score for a Runescape player name.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            player: Runescape playername to look up score for.
        """

        await interaction.response.defer(thinking=True)

        if player is None:
            player = interaction.user.display_name

        try:
            member, player = validate_user_request(interaction, player)
        except (ReferenceError, ValueError) as error:
            await send_error_response(interaction, str(error))
            return

        logger.info(
            (
                f"Handling '/score player:{player}' on behalf of "
                f"{normalize_discord_string(interaction.user.display_name)}"
            )
        )

        try:
            data = score_info(player)
        except RuntimeError as error:
            await send_error_response(interaction, str(error))
            return

        activities = data.clues + data.raids + data.bosses

        skill_points = 0
        for skill in data.skills:
            skill_points += skill["points"]

        activity_points = 0
        for activity in activities:
            activity_points += activity["points"]

        points_total = skill_points + activity_points
        rank_name = get_rank_from_points(points_total)
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(self._discord_client.emojis, rank_name)

        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()].value
        next_rank_icon = find_emoji(self._discord_client.emojis, next_rank_name)

        embed = build_response_embed(
            f"{rank_icon} {member.display_name}", "", rank_color
        )
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

    async def breakdown(
        self, interaction: discord.Interaction, player: Optional[str] = None
    ):
        """Compute player score with complete source enumeration.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            (optional) player: Runescape username to break down clan score for.
        """

        await interaction.response.defer(thinking=True)

        if player is None:
            player = interaction.user.display_name

        try:
            member, player = validate_user_request(interaction, player)
        except (ReferenceError, ValueError) as error:
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/breakdown player:{player}' on behalf of "
            f"{normalize_discord_string(interaction.user.display_name)}"
        )

        try:
            data = score_info(player)
        except RuntimeError as error:
            await send_error_response(interaction, str(error))
            return

        activities = data.clues + data.raids + data.bosses

        skill_points = 0
        for skill in data.skills:
            skill_points += skill["points"]

        activity_points = 0
        for activity in activities:
            activity_points += activity["points"]

        points_total = skill_points + activity_points
        rank_name = get_rank_from_points(points_total)
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(self._discord_client.emojis, rank_name)

        rank_breakdown_embed = build_response_embed(
            f"{rank_icon} {member.display_name} | Rank Ladder",
            "The **Iron Forged** player rank ladder.",
            rank_color,
        )

        for rank in RANKS:
            icon = find_emoji(self._discord_client.emojis, rank)
            rank_point_threshold = RANK_POINTS[rank.upper()].value
            rank_breakdown_embed.add_field(
                name=(
                    f"{icon} {rank}%s"
                    % (
                        f"{EMPTY_SPACE}{EMPTY_SPACE}{EMPTY_SPACE}{EMPTY_SPACE}{EMPTY_SPACE}"
                        f"<-- _You are here_"
                        if rank == rank_name
                        else ""
                    )
                ),
                value=f"{EMPTY_SPACE}{rank_point_threshold:,}+ points",
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
            f"{rank_icon} {member.display_name} | Skilling Points",
            f"Breakdown of **{skill_points:,}** points awarded for skill xp.",
            rank_color,
        )

        ordered_skills = sorted(data.skills, key=lambda x: x["display_order"])

        for skill in ordered_skills:
            skill_icon = find_emoji(self._discord_client.emojis, skill["emoji_key"])
            skill_breakdown_embed.add_field(
                name=f"{skill_icon} {skill['points']:,} points",
                value=f"{EMPTY_SPACE}{skill['xp']:,} xp",
                inline=True,
            )

        # empty field to maintain layout
        skill_breakdown_embed.add_field(
            name="",
            value="",
            inline=True,
        )

        # There is a 25 field limit on embeds, so we need to paginate.
        # As not every player has kc on every boss we don't need to show
        # all bosses, so this won't be as bad for some players.
        field_count = 0
        boss_embeds = []

        working_embed = build_response_embed(
            "",
            "",
            rank_color,
        )

        boss_point_counter = 0
        for boss in data.bosses:
            if boss["points"] < 1:
                continue

            if field_count == 24:
                field_count = 0
                boss_embeds.append((working_embed))
                working_embed = build_response_embed(
                    "",
                    "",
                    rank_color,
                )

            boss_point_counter += boss["points"]

            field_count += 1
            boss_icon = find_emoji(self._discord_client.emojis, boss["emoji_key"])
            working_embed.add_field(
                name=f"{boss_icon} {boss['points']:,} points",
                value=f"{EMPTY_SPACE}{boss['kc']:,} kc",
            )

        boss_embeds.append(working_embed)
        boss_page_count = len(boss_embeds)

        for index, embed in enumerate(boss_embeds):
            embed.title = f"{rank_icon} {member.display_name} | Bossing Points"
            embed.description = (
                f"Breakdown of **{boss_point_counter:,}** points awarded for boss kc."
            )

            if boss_page_count > 1:
                embed.title = "".join(embed.title) + f" ({index + 1}/{boss_page_count})"

            if index + 1 == boss_page_count:
                if len(embed.fields) % 3 != 0:
                    embed.add_field(name="", value="")

        raid_breakdown_embed = build_response_embed(
            f"{rank_icon} {member.display_name} | Raid Points",
            "",
            rank_color,
        )

        raid_point_counter = 0
        for raid in data.raids:
            raid_point_counter += raid["points"]
            raid_icon = find_emoji(self._discord_client.emojis, raid["emoji_key"])
            raid_breakdown_embed.add_field(
                name=f"{raid_icon} {raid['points']:,} points",
                value=f"{EMPTY_SPACE}{raid['kc']:,} kc",
            )

        raid_breakdown_embed.description = f"Breakdown of **{raid_point_counter:,}** points awarded for raid completions."

        clue_breakdown_embed = build_response_embed(
            f"{rank_icon} {member.display_name} | Cluescroll Points",
            "Points awarded for cluescroll completions.",
            rank_color,
        )

        clue_point_counter = 0
        clue_icon = find_emoji(self._discord_client.emojis, "cluescroll")
        for clue in data.clues:
            clue_point_counter += clue["points"]
            clue_breakdown_embed.add_field(
                name=f"{clue_icon} {clue['points']:,} points",
                value=f"{EMPTY_SPACE}{clue['kc']:,} {clue.get("display_name", clue['name'])}",
            )

        clue_breakdown_embed.description = f"Breakdown of **{clue_point_counter:,}** points awarded for cluescroll completions."

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

    async def ingots(
        self, interaction: discord.Interaction, player: Optional[str] = None
    ):
        """View your ingots, or those for another player.

        Arguments:
            interaction: Discord Interaction from CommandTree.
            (optional) player: Runescape username to view ingot count for.
        """

        await interaction.response.defer(thinking=True)

        if player is None:
            player = interaction.user.display_name

        try:
            _, player = validate_user_request(interaction, player)
        except (ReferenceError, ValueError) as error:
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/ingots player:{player}' on behalf of {normalize_discord_string(interaction.user.display_name)}"
        )

        try:
            member = self._storage_client.read_member(player.lower())
        except StorageError as error:
            await send_error_response(interaction, str(error))
            return

        if member is None:
            await send_error_response(
                interaction, f"Member '{player}' not found in spreadsheet"
            )
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

        await interaction.response.defer()

        try:
            caller, player = validate_protected_request(
                interaction, player, ROLES.LEADERSHIP
            )
        except (ReferenceError, ValueError) as error:
            logger.info(
                f"Member '{interaction.user.display_name}' tried addingingots does not have permission"
            )
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/addingots player:{player} ingots:{ingots} reason:{reason}' on behalf of {interaction.user.display_name}"
        )

        try:
            member = self._storage_client.read_member(player.lower())
        except StorageError as error:
            await send_error_response(interaction, str(error))
            return

        if member is None:
            await send_error_response(
                interaction, f"Member '{player}' not found in spreadsheet"
            )
            return

        member.ingots += ingots

        try:
            self._storage_client.update_members(
                [member], caller.display_name, note=reason
            )
        except StorageError as error:
            await send_error_response(interaction, f"Error updating ingots: {error}")
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

        await interaction.response.defer()

        try:
            _, caller = validate_protected_request(
                interaction, interaction.user.display_name, ROLES.LEADERSHIP
            )
        except (ReferenceError, ValueError) as error:
            logger.info(
                f"Member '{interaction.user.display_name}' tried addingingots does not have permission"
            )
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/addingotsbulk players:{players} ingots:{ingots} reason:{reason}' on behalf of {caller}"
        )

        player_names = players.split(",")
        player_names = [player.strip() for player in player_names]
        for player in player_names:
            try:
                validate_playername(player)
            except ValueError as error:
                await send_error_response(interaction, str(error))

        try:
            members = self._storage_client.read_members()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading member '{error}'"
            )
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
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error writing ingots for '{error}'"
            )
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

        await interaction.response.defer()

        try:
            caller, player = validate_protected_request(
                interaction, player, ROLES.LEADERSHIP
            )
        except (ReferenceError, ValueError) as error:
            logger.info(
                f"Member '{interaction.user.display_name}' tried updateingots but does not have permission"
            )
            await send_error_response(interaction, str(error))
            return

        logger.info(
            f"Handling '/updateingots player:{player} ingots:{ingots} reason:{reason}' on behalf of {caller}"
        )

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
            self._storage_client.update_members(
                [member], caller.display_name, note=reason
            )
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
        await cmd_sync_members(interaction, self._discord_client.discord_guild, self._storage_client)


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
