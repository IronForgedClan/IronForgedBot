import logging
import discord

from ironforgedbot.common.helpers import find_emoji, validate_protected_request
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import StorageError


logger = logging.getLogger(__name__)


async def add_ingots(
    self,
    interaction: discord.Interaction,
    player: str,
    ingots: int,
    reason: str = "None",
):
    """Add ingots to a Runescape alias.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to add ingots to.
        ingots: number of ingots to add to this player.
    """

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
        member = self._storage_client.read_member(player.lower())
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
        self._storage_client.update_members([member], caller.display_name, note=reason)
    except StorageError as error:
        await send_error_response(interaction, f"Error updating ingots: {error}")
        return

    ingot_icon = find_emoji(self._discord_client.emojis, "Ingot")
    await interaction.followup.send(
        f"Added {ingots:,} ingots to {player}; reason: {reason}. They now have {member.ingots:,} ingots {ingot_icon}"
    )
