import logging

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.commands.breakdown import breakdown
from ironforgedbot.commands.ingots.add_ingots import add_ingots
from ironforgedbot.commands.ingots.add_ingots_bulk import add_ingots_bulk
from ironforgedbot.commands.ingots.update_ingots import update_ingots
from ironforgedbot.commands.ingots.view_ingots import view_ingots
from ironforgedbot.commands.log_access import log_access
from ironforgedbot.commands.raffle.raffle_admin import raffle_admin
from ironforgedbot.commands.raffle.raffle_buy_tickets import raffle_buy_tickets
from ironforgedbot.commands.raffle.raffle_tickets import raffle_view_tickets
from ironforgedbot.commands.roster.roster import cmd_roster
from ironforgedbot.commands.score import score
from ironforgedbot.commands.sync_members import sync_members

logger = logging.getLogger(__name__)


class IronForgedCommands:
    def __init__(
        self,
        tree: discord.app_commands.CommandTree,
        discord_client: DiscordClient,
    ):
        self._tree = tree
        self._discord_client = discord_client

        self._tree.add_command(
            discord.app_commands.Command(
                name="score",
                description="Displays player score.",
                callback=score,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="breakdown",
                description="Displays player score breakdown.",
                callback=breakdown,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="ingots",
                description="Displays ingot total.",
                callback=view_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="add_ingots",
                description="Add or remove member's ingots.",
                callback=add_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="add_ingots_bulk",
                description="Add or remove ingots for multiple members.",
                callback=add_ingots_bulk,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="update_ingots",
                description="Set a members's ingot total to a new value.",
                callback=update_ingots,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="raffle_admin",
                description="Raffle admin actions.",
                callback=raffle_admin,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="raffle_tickets",
                description="Displays member's raffle ticket total.",
                callback=raffle_view_tickets,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="buy_raffle_tickets",
                description="Buy raffle tickets (5k ingots each).",
                callback=raffle_buy_tickets,
            )
        )
        self._tree.add_command(
            discord.app_commands.Command(
                name="sync_members",
                description="Synchronises Discord with storage.",
                callback=sync_members,
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
                callback=log_access,
            )
        )
