import logging

import discord

from ironforgedbot.commands.spin.build_spin_webm import build_spin_webm_file
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)


def _parse_options(options_str: str) -> list[str] | None:
    parsed = [o.strip() for o in options_str.split(",") if o.strip()]
    if len(parsed) < 2:
        return None
    return parsed


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@discord.app_commands.describe(options="Comma-separated list of options to spin (minimum 2)")
async def cmd_spin(interaction: discord.Interaction, options: str) -> None:
    parsed = _parse_options(options)
    if parsed is None:
        await send_error_response(
            interaction,
            "Please provide at least 2 comma-separated options to spin.",
        )
        return

    try:
        file, _winner = await build_spin_webm_file(parsed)
    except Exception as e:
        logger.error(f"Error generating spin GIF: {e}")
        await send_error_response(
            interaction,
            "Failed to generate spin animation. Please try again later.",
        )
        return

    await interaction.followup.send(file=file)
