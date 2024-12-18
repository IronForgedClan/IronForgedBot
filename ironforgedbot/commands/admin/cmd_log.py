import datetime
import logging
import os
from typing import Optional

import discord

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role
from ironforgedbot.logging_config import LOG_DIR

logger = logging.getLogger(__name__)


@require_role(ROLE.DISCORD_TEAM, ephemeral=True)
async def cmd_log(interaction: discord.Interaction, file_index: Optional[int]):
    """Allows access to logs through Discord.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        file_index: Optional - The index of the file you want to view.
    """
    embed = build_response_embed("🗃️ Bot Logs", "", discord.Color.blurple())
    logs = os.listdir(LOG_DIR)

    if file_index is not None and file_index > 0 and file_index <= len(logs) - 1:
        await interaction.followup.send(
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

    await interaction.followup.send(embed=embed, ephemeral=True)
