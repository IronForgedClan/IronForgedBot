import logging

import discord
from discord import app_commands

from ironforgedbot.commands.leaderboard.leaderboard_embeds import (
    build_leaderboard_embeds,
    find_caller_page,
)
from ironforgedbot.commands.leaderboard.leaderboard_menu import (
    LeaderboardMenu,
    build_leaderboard_menu,
)
from ironforgedbot.commands.leaderboard.leaderboard_types import LEADERBOARD_TYPES
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.database.database import db
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(leaderboard_type="The leaderboard to display.")
@app_commands.rename(leaderboard_type="type")
@app_commands.choices(
    leaderboard_type=[
        app_commands.Choice(name="Ingot", value="ingots"),
        app_commands.Choice(name="Score", value="score"),
    ]
)
async def cmd_leaderboard(
    interaction: discord.Interaction,
    leaderboard_type: app_commands.Choice[str],
) -> None:
    config = LEADERBOARD_TYPES[leaderboard_type.value]

    async with db.get_session() as session:
        entries = await config.fetcher(session)

    entries.sort(key=config.sort_key, reverse=True)

    caller_page = find_caller_page(entries, interaction.user.id)
    embeds = build_leaderboard_embeds(entries, config)
    menu = build_leaderboard_menu(interaction, embeds, caller_page)

    try:
        await menu.start()
    except Exception as e:
        logger.error(f"Error starting leaderboard menu: {e}", exc_info=True)
        try:
            await menu.stop()
        except Exception as stop_error:
            logger.warning(f"Error stopping leaderboard menu: {stop_error}")
        await send_error_response(
            interaction,
            "An unexpected error occurred while generating the leaderboard. Please try again.",
        )
