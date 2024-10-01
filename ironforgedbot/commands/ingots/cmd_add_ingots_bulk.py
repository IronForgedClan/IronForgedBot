import logging
import os
from typing import Optional

import discord

from ironforgedbot.common.helpers import normalize_discord_string, validate_playername
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLES.LEADERSHIP)
async def cmd_add_ingots_bulk(
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
    if not reason:
        reason = "None"

    caller = normalize_discord_string(interaction.user.display_name)

    player_names = players.split(",")
    sanitized_player_names = []

    assert interaction.guild

    for player in player_names:
        try:
            _, name = validate_playername(interaction.guild, player.strip())
            sanitized_player_names.append(name)
        except ValueError as e:
            await send_error_response(interaction, str(e))

    try:
        members = await STORAGE.read_members()
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error reading member '{error}'"
        )
        return

    output = []
    members_to_update = []
    for player in sanitized_player_names:
        found = False
        for member in members:
            if member.runescape_name.lower() == player.lower():
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
        await STORAGE.update_members(members_to_update, caller, note=reason)
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
