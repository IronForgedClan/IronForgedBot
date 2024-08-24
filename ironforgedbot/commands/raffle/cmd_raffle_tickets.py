import logging

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def cmd_raffle_tickets(interaction: discord.Interaction):
    """View calling user's current raffle ticket count."""
    await interaction.response.defer(thinking=True)

    caller = normalize_discord_string(interaction.user.display_name)

    logger.info(f"Handling '/raffle_tickets' on behalf of {caller}")

    try:
        member = STORAGE.read_member(caller)
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
        current_tickets = STORAGE.read_raffle_tickets()
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
