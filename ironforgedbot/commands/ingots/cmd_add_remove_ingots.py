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
    total_change = 0
    sanitized_player_names = set()
    members_to_update = []
    output_data = []

    assert interaction.guild

    for player in players.split(","):
        player = player.strip()

        if len(player) < 1:
            continue

        try:
            if player in sanitized_player_names:
                logger.info(f"Ignoring duplicate player: {player}")
                continue

            _, name = validate_playername(interaction.guild, player)
            sanitized_player_names.add(name)
        except ValueError as _:
            logger.info(f"Ignoring unknown player: {player}")
            output_data.append([player, 0, "unknown"])

    try:
        members = await STORAGE.read_members()
    except StorageError as error:
        logger.error(error)
        return await send_error_response(interaction, "Error reading member data.")

    for player in sorted(sanitized_player_names):
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
                    output_data.append(
                        [
                            player,
                            0,
                            f"{member.ingots:,}",
                        ]
                    )
                    break

                total_change += ingots
                member.ingots = new_total
                members_to_update.append(member)
                output_data.append(
                    [
                        player,
                        f"{'+' if is_positive else ''}{ingots:,}",
                        f"{member.ingots:,}",
                    ]
                )
                break

    try:
        await STORAGE.update_members(
            members_to_update,
            normalize_discord_string(interaction.user.display_name),
            note=reason,
        )
    except StorageError as error:
        logger.error(error)
        return await send_error_response(interaction, "Error updating ingot values.")

    ingot_icon = find_emoji(None, "Ingot")
    sorted_output_data = sorted(output_data, key=lambda row: row[0])
    result_table = tabulate(
        sorted_output_data, headers=["Player", "Change", "Total"], tablefmt="github"
    )
    result_title = f"{ingot_icon} {'Add' if is_positive else 'Remove'} Ingot Results"
    result_content = (
        f"**Total Change:** {'+' if is_positive else ''}{total_change:,}\n"
        f"**Reason:** _{reason}_"
    )

    if len(output_data) >= 9:
        discord_file = discord.File(
            fp=io.BytesIO(result_table.encode("utf-8")),
            description="example description",
            filename=f"ingot_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt",
        )

        return await interaction.followup.send(
            f"## {result_title}\n{result_content}",
            file=discord_file,
        )

    embed = build_ingot_response_embed(result_title, result_content)

    embed.add_field(name="", value=f"```{result_table}```")
    return await interaction.followup.send(embed=embed)
