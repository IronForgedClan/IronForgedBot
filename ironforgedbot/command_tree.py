import logging
import traceback

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.commands.admin.cmd_admin import cmd_admin
from ironforgedbot.commands.admin.cmd_get_role_members import cmd_get_role_members
from ironforgedbot.commands.debug.cmd_debug_commands import cmd_debug_commands
from ironforgedbot.commands.debug.cmd_stress_test import cmd_stress_test
from ironforgedbot.commands.hiscore.cmd_breakdown import cmd_breakdown
from ironforgedbot.commands.hiscore.cmd_score import cmd_score
from ironforgedbot.commands.holiday.cmd_trick_or_treat import cmd_trick_or_treat
from ironforgedbot.commands.ingots.cmd_add_remove_ingots import cmd_add_remove_ingots
from ironforgedbot.commands.ingots.cmd_view_ingots import cmd_view_ingots
from ironforgedbot.commands.lookup.cmd_whois import cmd_whois
from ironforgedbot.commands.raffle.cmd_raffle import cmd_raffle
from ironforgedbot.commands.roster.cmd_roster import cmd_roster
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.commands.help.cmd_help import cmd_help
from ironforgedbot.config import CONFIG, ENVIRONMENT

logger = logging.getLogger(__name__)


class IronForgedCommandTree(discord.app_commands.CommandTree):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        if isinstance(error, discord.app_commands.CheckFailure):
            logger.info(error)
            await interaction.response.defer(thinking=True, ephemeral=True)
            return await send_error_response(
                interaction,
                "You do not have permission to run that command.",
            )

        logger.critical(f"Error: {error}\n%s", traceback.format_exc())
        return await send_error_response(
            interaction,
            (
                "An unhandled error has occurred.\n"
                f"Please alert a member of the {text_bold('Discord Team')}."
            ),
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
        )  # ROLE:MEMBER | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="breakdown",
                description="Displays player score breakdown.",
                callback=cmd_breakdown,
            )
        )  # ROLE:MEMBER | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="ingots",
                description="Displays ingot total.",
                callback=cmd_view_ingots,
            )
        )  # ROLE:MEMBER | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="add_remove_ingots",
                description="Add or remove ingots to one or multiple member's accounts.",
                callback=cmd_add_remove_ingots,
            )
        )  # ROLE:LEADERSHIP | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="roster",
                description="Creates an event roster.",
                callback=cmd_roster,
            )
        )  # ROLE:LEADERSHIP | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="whois",
                description="Get player's rsn history.",
                callback=cmd_whois,
            )
        )  # ROLE:MEMBER | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="get_role_members",
                description="Generate a list of all members with a certain role.",
                callback=cmd_get_role_members,
            )
        )  # ROLE:LEADERSHIP | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="raffle",
                description="Play or control the raffle.",
                callback=cmd_raffle,
            )
        )  # ROLE:LEADERSHIP | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="admin",
                description="Collection of administrative actions.",
                callback=cmd_admin,
            )
        )  # ROLE:LEADERSHIP | TYPE:PERMANENT

        self._tree.add_command(
            discord.app_commands.Command(
                name="help",
                description="Show a list of available commands.",
                callback=cmd_help,
            )
        )  # ROLE:MEMBER | TYPE:PERMANENT

        if CONFIG.TRICK_OR_TREAT_ENABLED:
            self._tree.add_command(
                discord.app_commands.Command(
                    name="trick_or_treat",
                    description="Feeling lucky, punk?",
                    callback=cmd_trick_or_treat,
                )
            )  # ROLE:MEMBER | TYPE:HOLIDAY | RANGE:10/1-11/1

        if CONFIG.ENVIRONMENT in [ENVIRONMENT.DEVELOPMENT, ENVIRONMENT.STAGING]:
            self._tree.add_command(
                discord.app_commands.Command(
                    name="debug_commands",
                    description="Menu showing all commands",
                    callback=cmd_debug_commands,
                )
            )  # DEV-ONLY

            self._tree.add_command(
                discord.app_commands.Command(
                    name="stress_test",
                    description="Stress test",
                    callback=cmd_stress_test,
                )
            )  # DEV-ONLY
