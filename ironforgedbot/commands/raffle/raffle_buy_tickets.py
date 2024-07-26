import logging
import discord

from ironforgedbot.common.helpers import validate_user_request
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def raffle_buy_tickets(self, interaction: discord.Interaction, tickets: int):
    """Use ingots to buy tickets. Tickets cost 5000 ingots each."""

    try:
        _, caller = validate_user_request(interaction, interaction.user.display_name)
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
