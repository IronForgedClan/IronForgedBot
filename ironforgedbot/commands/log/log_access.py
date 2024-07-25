import datetime
import logging
import os
from typing import Optional

import discord

from ironforgedbot.common.helpers import validate_protected_request
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLES


logger = logging.getLogger(__name__)


async def log_access(interaction: discord.Interaction, file_index: Optional[int]):
    """Allows access to logs through Discord.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        file_index: Optional - The index of the file you want to view.
    """
    try:
        validate_protected_request(
            interaction, interaction.user.display_name, ROLES.DISCORD_TEAM
        )
    except (ReferenceError, ValueError) as error:
        await interaction.response.defer()
        logger.info(
            f"Member '{interaction.user.display_name}' tried using log but does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    logger.info(
        f"Handling '/logs file_index:{file_index}' on behalf of {interaction.user.display_name}"
    )

    embed = build_response_embed("🗃️ Iron Forged Bot Logs", "", discord.Color.blurple())
    log_dir = os.listdir("./logs")

    if file_index is not None and file_index > 0 and file_index <= len(log_dir) - 1:
        await interaction.response.send_message(
            file=discord.File(f"./logs/{log_dir[file_index]}"), ephemeral=True
        )
        return

    for index, file in enumerate(log_dir):
        if "lock" in file:
            continue

        file_size = round(os.path.getsize(f"./logs/{file}") / 1024, 0)
        file_modified = datetime.datetime.strftime(
            datetime.datetime.fromtimestamp(os.path.getmtime(f"./logs/{file}")),
            "%Y-%m-%d %H:%M:%S",
        )

        embed.add_field(
            name="",
            value=f"**[{index}]** {file_modified} [{file_size}kb] -- {file}",
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)
