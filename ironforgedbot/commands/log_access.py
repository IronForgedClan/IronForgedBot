import datetime
import logging
import os
from typing import Optional

import discord

from ironforgedbot.commands.hiscore.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import validate_protected_request
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.logging_config import LOG_DIR


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

    embed = build_response_embed("🗃️ Bot Logs", "", discord.Color.blurple())
    logs = os.listdir(LOG_DIR)

    if file_index is not None and file_index > 0 and file_index <= len(logs) - 1:
        await interaction.response.send_message(
            file=discord.File(f"{LOG_DIR}/{logs[file_index]}"), ephemeral=True
        )
        return

    for index, file in enumerate(logs):
        if "lock" in file:
            continue

        file_size = round(os.path.getsize(f"{LOG_DIR}/{file}") / 1024, 0)
        file_modified = datetime.datetime.strftime(
            datetime.datetime.fromtimestamp(os.path.getmtime(f"{LOG_DIR}/{file}")),
            "%Y-%m-%d %H:%M:%S",
        )

        embed.add_field(
            name="",
            value=f"**[{index}]** {file_modified}\n{EMPTY_SPACE}_{file}_{EMPTY_SPACE}{file_size}kb",
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)
