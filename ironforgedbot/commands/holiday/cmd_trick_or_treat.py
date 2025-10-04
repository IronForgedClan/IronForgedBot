import logging

import discord

from ironforgedbot.commands.holiday.trick_or_treat_handler import get_handler
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import rate_limit, require_channel, require_role

logger = logging.getLogger(__name__)


@require_channel([CONFIG.TRICK_OR_TREAT_CHANNEL_ID])
@rate_limit(1, CONFIG.TRICK_OR_TREAT_COOLDOWN_SECONDS)
@require_role(ROLE.MEMBER)
@log_command_execution(logger)
async def cmd_trick_or_treat(interaction: discord.Interaction):
    handler = get_handler()
    return await handler.random_result(interaction)
