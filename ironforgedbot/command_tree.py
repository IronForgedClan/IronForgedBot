import logging

import discord
import traceback

from ironforgedbot.client import DiscordClient
from ironforgedbot.commands.admin.cmd_activity_check import cmd_activity_check
from ironforgedbot.commands.admin.cmd_log import cmd_log
from ironforgedbot.commands.admin.cmd_sync_members import cmd_sync_members
from ironforgedbot.commands.hiscore.cmd_breakdown import cmd_breakdown
from ironforgedbot.commands.hiscore.cmd_score import cmd_score
from ironforgedbot.commands.holiday.cmd_trick_or_treat import cmd_trick_or_treat
from ironforgedbot.commands.ingots.cmd_add_remove_ingots import cmd_add_remove_ingots
from ironforgedbot.commands.ingots.cmd_update_ingots import cmd_update_ingots
from ironforgedbot.commands.ingots.cmd_view_ingots import cmd_view_ingots
from ironforgedbot.commands.lookup.cmd_whois import cmd_whois
from ironforgedbot.commands.raffle.cmd_raffle_admin import cmd_raffle_admin
from ironforgedbot.commands.raffle.cmd_raffle_buy_tickets import cmd_buy_raffle_tickets
from ironforgedbot.commands.raffle.cmd_raffle_tickets import cmd_raffle_tickets
from ironforgedbot.commands.roster.cmd_roster import cmd_roster
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


class IronForgedCommandTree(discord.app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        logger.critical(f"Error: {error}\n%s", traceback.format_exc())

        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.defer(thinking=True, ephemeral=True)
            return await send_error_response(
                interaction,
                "You do not have permission to run that command.",
            )

        return await send_error_response(
            interaction,
            "An unhandled error has occured.\nPlease alert a member of the **Discord Team**.",
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
                callback=cmd_view_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="add_remove_ingots",
                description="Add or remove ingots to one or multiple member's accounts.",
                callback=cmd_add_remove_ingots,
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
        self._tree.add_command(
            discord.app_commands.Command(
                name="whois",
                description="Get player's rsn history.",
                callback=cmd_whois,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="activity_check",
                description="Manually runs the activity check automation.",
                callback=cmd_activity_check,
            )
        )
        if CONFIG.TRICK_OR_TREAT_ENABLED:
            self._tree.add_command(
                discord.app_commands.Command(
                    name="trick_or_treat",
                    description="Feeling lucky, punk?",
                    callback=cmd_trick_or_treat,
                )
            )
