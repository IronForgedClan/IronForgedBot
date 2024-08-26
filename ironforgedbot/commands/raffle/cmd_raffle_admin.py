import logging

import discord

from ironforgedbot.commands.raffle.cmd_raffle_end import sub_raffle_end
from ironforgedbot.commands.raffle.cmd_raffle_select_winner import sub_raffle_select_winner
from ironforgedbot.commands.raffle.cmd_raffle_start import sub_raffle_start
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role

logger = logging.getLogger(__name__)


@require_role(ROLES.LEADERSHIP)
async def cmd_raffle_admin(interaction: discord.Interaction, command: str):
    """Parent command for doing admin actions around raffles.

    Args:
        command: string of admin action to perform. Valid actions: [start, end, select_winner].
            'start_raffle' will open purchasing of tickets, 'end_raffle' will close
            purchasing, and 'choose_winner' will choose a winner & display
            their winnings (alongside clearing storage for the next raffle).
    """
    if command.lower() == "start":
        await sub_raffle_start(interaction)
    elif command.lower() == "end":
        await sub_raffle_end(interaction)
    elif command.lower() == "select_winner":
        await sub_raffle_select_winner(interaction)
    else:
        await interaction.followup.send("provided subcommand is not implemented")
