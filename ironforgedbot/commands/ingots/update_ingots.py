import logging

import discord

from ironforgedbot.common.helpers import find_emoji, validate_protected_request
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import StorageError


logger = logging.getLogger(__name__)


async def update_ingots(
    self,
    interaction: discord.Interaction,
    player: str,
    ingots: int,
    reason: str = "None",
):
    """Set ingots for a Runescape alias.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to view ingot count for.
        ingots: New ingot count for this user.
    """

    try:
        caller, player = validate_protected_request(
            interaction, player, ROLES.LEADERSHIP
        )
    except (ReferenceError, ValueError) as error:
        logger.info(
            f"Member '{interaction.user.display_name}' tried updateingots but does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    logger.info(
        f"Handling '/updateingots player:{player} ingots:{ingots} reason:{reason}' on behalf of {caller}"
    )

    try:
        member = self._storage_client.read_member(player.lower())
    except StorageError as e:
        await interaction.followup.send(f"Encountered error reading member: {e}")
        return

    if member is None:
        await interaction.followup.send(f"{player} wasn't found.")
        return

    member.ingots = ingots

    try:
        self._storage_client.update_members([member], caller.display_name, note=reason)
    except StorageError as e:
        await interaction.followup.send(f"Encountered error writing ingots: {e}")
        return

    ingot_icon = find_emoji(self._discord_client.emojis, "Ingot")
    await interaction.followup.send(
        f"Set ingot count to {ingots:,} for {player}. Reason: {reason} {ingot_icon}"
    )