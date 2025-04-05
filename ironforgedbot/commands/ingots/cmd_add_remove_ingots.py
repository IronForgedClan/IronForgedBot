import io
import logging
from datetime import datetime
from typing import Dict

import discord
from tabulate import tabulate

from ironforgedbot.common.helpers import (
    find_emoji,
    validate_playername,
)
from ironforgedbot.common.responses import (
    build_ingot_response_embed,
)
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import (
    text_bold,
    text_code_block,
    text_h2,
    text_italic,
)
from ironforgedbot.database.database import db
from ironforgedbot.decorators import require_role
from ironforgedbot.services.ingot_service import IngotService, IngotServiceResponse

logger = logging.getLogger(__name__)


@require_role(ROLE.LEADERSHIP)
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
    validated_players: Dict[str, discord.Member] = {}
    output_data = []

    assert interaction.guild

    for player in players.split(","):
        player = player.strip()

        if len(player) < 1:
            continue

        try:
            if player in validated_players:
                logger.info(f"Ignoring duplicate player: {player}")
                continue

            discord_member, name = validate_playername(
                interaction.guild, player, must_be_member=True
            )
            if discord_member:
                validated_players[name] = discord_member
        except ValueError:
            logger.info(f"Ignoring unknown player: {player}")
            output_data.append([player, 0, "unknown"])

    async for session in db.get_session():
        service = IngotService(session)

        for player, discord_member in validated_players.items():
            result = None
            if is_positive:
                result = await service.try_add_ingots(
                    discord_member.id, ingots, interaction.user.id, reason
                )
            else:
                result = await service.try_remove_ingots(
                    discord_member.id, ingots, interaction.user.id, reason
                )

            if result and isinstance(result, IngotServiceResponse):
                if result.status and result.new_total > -1:
                    total_change += ingots
                    output_data.append(
                        [
                            player,
                            f"{'+' if is_positive else ''}{ingots:,}",
                            f"{result.new_total:,}",
                        ]
                    )
                else:
                    output_data.append(
                        [
                            player,
                            "0",
                            f"{result.new_total:,}",
                        ]
                    )

                    logger.info(result.message)

    ingot_icon = find_emoji(None, "Ingot")
    sorted_output_data = sorted(output_data, key=lambda row: row[0])
    result_table = tabulate(
        sorted_output_data,
        headers=["Player", "Change", "Total"],
        tablefmt="github",
        colalign=("left", "right", "right"),
    )
    result_title = f"{ingot_icon} {'Add' if is_positive else 'Remove'} Ingots Result"
    result_content = (
        f"{text_bold('Total Change:')} {'+' if is_positive else ''}{total_change:,}\n"
        f"{text_bold('Reason:')} {text_italic(reason)}"
    )

    if len(output_data) >= 9:
        discord_file = discord.File(
            fp=io.BytesIO(result_table.encode("utf-8")),
            description="example description",
            filename=f"ingot_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )

        return await interaction.followup.send(
            f"{text_h2(result_title)}{result_content}",
            file=discord_file,
        )

    embed = build_ingot_response_embed(result_title, result_content)

    embed.add_field(name="", value=text_code_block(result_table))
    return await interaction.followup.send(embed=embed)
