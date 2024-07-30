import logging
from typing import Optional

import discord

from ironforgedbot.common.helpers import find_emoji, validate_protected_request
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_ingots(
    interaction: discord.Interaction,
    player: str,
    ingots: int,
    reason: Optional[str],
):
    """Add ingots to a Runescape alias.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to add ingots to.
        ingots: number of ingots to add to this player.
    """
    await interaction.response.defer(thinking=True)

    if not reason:
        reason = "None"

    try:
        caller, player = validate_protected_request(
            interaction, player, ROLES.LEADERSHIP
        )
    except (ReferenceError, ValueError) as error:
        logger.info(
            f"Member '{interaction.user.display_name}' tried addingingots does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    logger.info(
        f"Handling '/addingots player:{player} ingots:{ingots} reason:{reason}' on behalf of {interaction.user.display_name}"
    )

    try:
        member = STORAGE.read_member(player.lower())
    except StorageError as error:
        await send_error_response(interaction, str(error))
        return

    if member is None:
        await send_error_response(
            interaction, f"Member '{player}' not found in spreadsheet"
        )
        return

    member.ingots += ingots

    try:
        STORAGE.update_members([member], caller.display_name, note=reason)
    except StorageError as error:
        await send_error_response(interaction, f"Error updating ingots: {error}")
        return

    ingot_icon = find_emoji(interaction, "Ingot")
    await interaction.followup.send(
        f"\nAdded `{ingots:,}` ingots to `{player}`; reason: {reason}. They now have {member.ingots:,} ingots {ingot_icon}"
    )
