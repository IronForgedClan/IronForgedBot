import logging

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLE.ANY)
async def cmd_raffle_tickets(interaction: discord.Interaction):
    """View calling user's current raffle ticket count."""
    caller = normalize_discord_string(interaction.user.display_name)

    try:
        member = await STORAGE.read_member(caller)
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
        current_tickets = await STORAGE.read_raffle_tickets()
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
