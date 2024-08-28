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


@require_role(ROLES.ANY)
async def cmd_view_ingots(
    interaction: discord.Interaction, player: Optional[str] = None
):
    """View your ingots, or those for another player.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        (optional) player: Runescape username to view ingot count for.
    """
    if player is None:
        player = interaction.user.display_name

    assert interaction.guild

    try:
        member, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    try:
        member = STORAGE.read_member(player)
    except StorageError as error:
        await send_error_response(interaction, str(error))
        return

    if member is None:
        await send_error_response(
            interaction, f"Member '{player}' not found in storage."
        )
        return

    ingot_icon = find_emoji(interaction, "Ingot")
    await interaction.followup.send(
        f"{player} has {member.ingots:,} ingots {ingot_icon}"
    )
