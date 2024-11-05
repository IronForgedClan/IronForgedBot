import io
import logging
from datetime import datetime

import discord
from tabulate import tabulate

from ironforgedbot.common.helpers import (
    find_emoji,
    normalize_discord_string,
    validate_playername,
)
from ironforgedbot.common.responses import (
    build_ingot_response_embed,
    send_error_response,
)
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLES.LEADERSHIP)
async def cmd_add_remove_ingots(
    interaction: discord.Interaction,
    players: str,
    ingots: int,
    reason: str,
):
    """Add or remove player(s) ingots.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        players: Comma-separated list of playernames.
        ingots: Number of ingots to change.
        reason: Short string detailing the reason for change.
    """
    is_positive = True if ingots > 0 else False
    caller = normalize_discord_string(interaction.user.display_name)
    output = []

    assert interaction.guild

    player_names = players.split(",")
    sanitized_player_names = []

    for player in player_names:
        try:
            _, name = validate_playername(interaction.guild, player.strip())
            sanitized_player_names.append(name)
        except ValueError as _:
            output.append([name, 0, "unknown"])

    try:
        members = await STORAGE.read_members()
    except StorageError as error:
        logger.error(error)
        return await send_error_response(interaction, "Error fetching member data.")

    members_to_update = []
    for player in sanitized_player_names:
        for member in members:
            if member.runescape_name.lower() == player.lower():
                new_total = member.ingots + ingots
                if new_total < 0:
                    error_table = tabulate(
                        [
                            ["Available:", f"{member.ingots:,}"],
                            ["Change:", f"{ingots:,}"],
                        ],
                        tablefmt="plain",
                    )
                    await send_error_response(
                        interaction,
                        (
                            f"Member **{player}** does not have enough ingots.\n"
                            f"```{error_table}```"
                        ),
                    )
                    output.append(
                        [
                            player,
                            0,
                            f"{member.ingots:,}",
                        ]
                    )
                    break

                member.ingots = new_total
                members_to_update.append(member)
                output.append(
                    [
                        player,
                        f"{'+' if is_positive else ''}{ingots:,}",
                        f"{member.ingots:,}",
                    ]
                )
                break

    try:
        await STORAGE.update_members(members_to_update, caller, note=reason)
    except StorageError as error:
        logger.error(error)
        return await send_error_response(interaction, "Error updating ingot values.")

    ingot_icon = find_emoji(None, "Ingot")
    table = tabulate(output, headers=["Player", "Change", "Total"], tablefmt="github")
    result_title = f"{ingot_icon} {'Add' if is_positive else 'Remove'} Ingot Results"

    if len(output) >= 9:
        discord_file = discord.File(
            fp=io.BytesIO(table.encode("utf-8")),
            description="example description",
            filename=f"add_ingots_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt",
        )

        return await interaction.followup.send(
            (
                f"## {result_title}\n"
                f"**Change:** _{'+' if is_positive else ''}{ingots:,}_\n"
                f"**Reason:** _{reason}_"
            ),
            file=discord_file,
        )

    embed = build_ingot_response_embed(
        f"{result_title}",
        (
            f"**Change:** _{'+' if is_positive else ''}{ingots:,}_\n"
            f"**Reason:** _{reason}_"
        ),
    )

    embed.add_field(name="", value=f"```{table}```")
    return await interaction.followup.send(embed=embed)
