import logging

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLES.ANY)
async def cmd_buy_raffle_tickets(interaction: discord.Interaction, tickets: int):
    """Use ingots to buy tickets. Tickets cost 5000 ingots each."""
    caller = normalize_discord_string(interaction.user.display_name)

    if tickets <= 0:
        await send_error_response(
            interaction,
            "`tickets` must be a positive number.",
        )
        return

    try:
        ongoing_raffle = STORAGE.read_raffle()
    except StorageError as error:
        await send_error_response(
            interaction,
            f"Encountered error reading raffle status from storage: {error}",
        )
        return

    if not ongoing_raffle:
        await send_error_response(
            interaction,
            "There is no ongoing raffle. Tickets cannot be bought.",
        )
        return

    # First, read member to get Discord ID & ingot count
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
        STORAGE.update_members([member], caller, note="Bought raffle tickets")
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error updating member ingot count: {error}"
        )
        return

    try:
        STORAGE.add_raffle_tickets(member.id, tickets)
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error adding raffle tickets: {error}"
        )

        return

    await interaction.followup.send(
        f"{caller} successfully bought {tickets} tickets for {cost} ingots!"
    )
