import logging
from typing import Optional

import discord

from ironforgedbot.common.helpers import find_emoji, validate_playername
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLES.LEADERSHIP)
async def cmd_add_ingots(
    interaction: discord.Interaction,
    player: str,
    ingots: int,
    reason: Optional[str] = None,
):
    """Add ingots to a Runescape alias.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to add ingots to.
        ingots: number of ingots to add to this player.
    """
    if not reason:
        reason = "None"

    assert interaction.guild

    try:
        _, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    try:
        member = await STORAGE.read_member(player.lower())
    except StorageError as error:
        await send_error_response(interaction, str(error))
        return

    if member is None:
        await send_error_response(
            interaction, f"Member '{player}' not found in storage."
        )
        return

    member.ingots += ingots

    try:
        await STORAGE.update_members(
            [member], interaction.user.display_name, note=reason
        )
    except StorageError as error:
        await send_error_response(interaction, f"Error updating ingots: {error}")
        return

    ingot_icon = find_emoji(interaction, "Ingot")
    await interaction.followup.send(
        f"\nAdded `{ingots:,}` ingots to `{player}`; reason: {reason}. They now have {member.ingots:,} ingots {ingot_icon}."
    )
