import logging

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.commands.spin.spin_result_handler import send_spin_result
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.command_price import command_price
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)

MINIMUM_SPIN_OPTIONS = 3


def _parse_options(options_str: str) -> list[str] | None:
    parsed = [o.strip() for o in options_str.split(",") if o.strip()]
    if len(parsed) < MINIMUM_SPIN_OPTIONS:
        return None
    return parsed


@require_role(ROLE.MEMBER)
@command_price(3499)
@log_command_execution(logger)
@discord.app_commands.describe(
    options=f"Comma-separated list of options (minimum {MINIMUM_SPIN_OPTIONS})"
)
async def cmd_spin(interaction: discord.Interaction, options: str) -> None:
    await interaction.response.defer(ephemeral=True)

    parsed = _parse_options(options)
    if parsed is None:
        await send_error_response(
            interaction,
            f"Please provide at least {MINIMUM_SPIN_OPTIONS} comma-separated options to spin. No refunds.",
        )
        return

    try:
        file, winner = await build_spin_gif_file(parsed)
    except Exception as e:
        logger.error(f"Error generating spin GIF: {e}")
        await send_error_response(
            interaction,
            "Failed to generate spin animation. Please try again later.",
        )
        return

    await send_spin_result(
        interaction,
        file,
        winner,
        spin_type="user spin",
        emoji=None,
        use_padding=False,
        reactions=None,
    )
