import logging

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.commands.breakdown import cmd_breakdown
from ironforgedbot.commands.ingots.add_ingots import cmd_add_ingots
from ironforgedbot.commands.ingots.cmd_add_ingots_bulk import cmd_add_ingots_bulk
from ironforgedbot.commands.ingots.update_ingots import cmd_update_ingots
from ironforgedbot.commands.ingots.view_ingots import cmd_ingots
from ironforgedbot.commands.raffle.raffle_admin import cmd_raffle_admin
from ironforgedbot.commands.raffle.raffle_buy_tickets import cmd_buy_raffle_tickets
from ironforgedbot.commands.raffle.raffle_tickets import cmd_raffle_tickets
from ironforgedbot.commands.roster.roster import cmd_roster
from ironforgedbot.commands.score import cmd_score
from ironforgedbot.commands.sync_members import cmd_sync_members
from ironforgedbot.commands.log_access import cmd_log
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


class IronForgedCommandTree(discord.app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        if isinstance(error, discord.app_commands.CheckFailure):
            logger.warning(error)

            await interaction.response.defer(thinking=True, ephemeral=True)
            return await send_error_response(
                interaction,
                "You do not have permission to run that command.",
            )

        logger.critical(error)

        await interaction.response.defer(thinking=True)
        return await send_error_response(
            interaction,
            "An unhandled error has occured. Please alert a member of the Discord Team.",
        )


class IronForgedCommands:
    def __init__(
        self,
        tree: IronForgedCommandTree,
        discord_client: DiscordClient,
    ):
        self._tree = tree
        self._discord_client = discord_client

        self._tree.add_command(
            discord.app_commands.Command(
                name="score",
                description="Displays player score.",
                callback=cmd_score,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="breakdown",
                description="Displays player score breakdown.",
                callback=cmd_breakdown,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="ingots",
                description="Displays ingot total.",
                callback=cmd_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="add_ingots",
                description="Add or remove member's ingots.",
                callback=cmd_add_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="add_ingots_bulk",
                description="Add or remove ingots for multiple members.",
                callback=cmd_add_ingots_bulk,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="update_ingots",
                description="Set a members's ingot total to a new value.",
                callback=cmd_update_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="raffle_admin",
                description="Raffle admin actions.",
                callback=cmd_raffle_admin,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="raffle_tickets",
                description="Displays member's raffle ticket total.",
                callback=cmd_raffle_tickets,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="buy_raffle_tickets",
                description="Buy raffle tickets (5k ingots each).",
                callback=cmd_buy_raffle_tickets,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="sync_members",
                description="Synchronises Discord with storage.",
                callback=cmd_sync_members,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="roster",
                description="Creates an event roster.",
                callback=cmd_roster,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="logs",
                description="Displays bot logs.",
                callback=cmd_log,
            )
        )
