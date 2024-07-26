import logging
from typing import Optional
import discord

from ironforgedbot.common.helpers import (
    find_emoji,
    normalize_discord_string,
    validate_user_request,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.storage.types import StorageError


logger = logging.getLogger(__name__)


async def view_ingots(
    self, interaction: discord.Interaction, player: Optional[str] = None
):
    """View your ingots, or those for another player.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        (optional) player: Runescape username to view ingot count for.
    """

    if player is None:
        player = interaction.user.display_name

    try:
        _, player = validate_user_request(interaction, player)
    except (ReferenceError, ValueError) as error:
        await send_error_response(interaction, str(error))
        return

    logger.info(
        f"Handling '/ingots player:{player}' on behalf of {normalize_discord_string(interaction.user.display_name)}"
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

    ingot_icon = find_emoji(self._discord_client.emojis, "Ingot")
    await interaction.followup.send(
        f"{player} has {member.ingots:,} ingots {ingot_icon}"
    )
