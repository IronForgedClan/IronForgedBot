import logging
from typing import Optional

import discord

from ironforgedbot.common.helpers import (
    find_emoji,
    normalize_discord_string,
    validate_playername,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLES.LEADERSHIP)
async def cmd_update_ingots(
    interaction: discord.Interaction,
    player: str,
    ingots: int,
    reason: Optional[str] = None,
):
    """Set ingots for a Runescape alias.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to view ingot count for.
        ingots: New ingot count for this user.
    """
    if not reason:
        reason = "None"

    caller = normalize_discord_string(interaction.user.display_name)

    assert interaction.guild

    try:
        _, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    try:
        member = await STORAGE.read_member(player.lower())
    except StorageError as e:
        await interaction.followup.send(f"Encountered error reading member: {e}")
        return

    if member is None:
        await interaction.followup.send(f"{player} wasn't found.")
        return

    member.ingots = ingots

    try:
        await STORAGE.update_members([member], caller, note=reason)
    except StorageError as e:
        await interaction.followup.send(f"Encountered error writing ingots: {e}")
        return

    ingot_icon = find_emoji(interaction, "Ingot")
    await interaction.followup.send(
        f"Set ingot count to {ingots:,} for {player}. Reason: {reason} {ingot_icon}"
    )
