import logging
import os
from typing import Optional

import discord

from ironforgedbot.common.helpers import validate_playername, validate_protected_request
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.config import CONFIG
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_ingots_bulk(
    interaction: discord.Interaction,
    players: str,
    ingots: int,
    reason: Optional[str] = None,
):
    """Add ingots to a Runescape alias.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Comma-separated list of Runescape usernames to add ingots to.
        ingots: number of ingots to add to this player.
    """
    await interaction.response.defer(thinking=True)

    if not reason:
        reason = "None"

    try:
        _, caller = validate_protected_request(
            interaction, interaction.user.display_name, ROLES.LEADERSHIP
        )
    except (ReferenceError, ValueError) as error:
        logger.info(
            f"Member '{interaction.user.display_name}' tried addingingots does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    logger.info(
        f"Handling '/addingotsbulk players:{players} ingots:{ingots} reason:{reason}' on behalf of {caller}"
    )

    player_names = players.split(",")
    player_names = [player.strip() for player in player_names]
    for player in player_names:
        try:
            validate_playername(player)
        except ValueError as error:
            await send_error_response(interaction, str(error))

    try:
        members = STORAGE.read_members()
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error reading member '{error}'"
        )
        return

    output = []
    members_to_update = []
    for player in player_names:
        found = False
        for member in members:
            if member.runescape_name == player.lower():
                found = True
                member.ingots += ingots
                members_to_update.append(member)
                output.append(
                    f"Added {ingots:,} ingots to {player}. They now have {member.ingots:,} ingots"
                )
                break
        if not found:
            output.append(f"{player} not found in storage.")

    try:
        STORAGE.update_members(members_to_update, caller, note=reason)
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error writing ingots for '{error}'"
        )
        return

    # Our output can be larger than the interaction followup max.
    # Send it in a file to accomodate this.
    path = os.path.join(CONFIG.TEMP_DIR, f"addingotsbulk_{caller}.txt")
    with open(path, "w") as f:
        f.write("\n".join(output))

    with open(path, "rb") as f:
        discord_file = discord.File(f, filename="addingotsbulk.txt")
        await interaction.followup.send(
            f"Added ingots to multiple members! Reason: {reason}", file=discord_file
        )
