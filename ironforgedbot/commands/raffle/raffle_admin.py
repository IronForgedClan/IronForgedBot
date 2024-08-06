import logging

import discord

from ironforgedbot.commands.raffle.raffle_end import sub_raffle_end
from ironforgedbot.commands.raffle.raffle_select_winner import sub_raffle_select_winner
from ironforgedbot.commands.raffle.raffle_start import sub_raffle_start
from ironforgedbot.common.helpers import (
    normalize_discord_string,
    validate_protected_request,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES

logger = logging.getLogger(__name__)


async def raffle_admin(interaction: discord.Interaction, subcommand: str):
    """Parent command for doing admin actions around raffles.

    Args:
        subcommand: string of admin action to perform. Valid actions: [start, end, choose_winner].
            'start_raffle' will open purchasing of tickets, 'end_raffle' will close
            purchasing, and 'choose_winner' will choose a winner & display
            their winnings (alongside clearing storage for the next raffle).
    """
    await interaction.response.defer(thinking=True)

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
    if subcommand.lower() == "start":
        await sub_raffle_start(interaction)
    elif subcommand.lower() == "end":
        await sub_raffle_end(interaction)
    elif subcommand.lower() == "choose_winner":
        await sub_raffle_select_winner(interaction)
    else:
        await interaction.followup.send("provided subcommand is not implemented")
