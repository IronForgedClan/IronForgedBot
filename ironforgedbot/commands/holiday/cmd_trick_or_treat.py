import logging

import discord

from ironforgedbot.commands.holiday.trick_or_treat_handler import TrickOrTreatHandler
from ironforgedbot.common.roles import ROLES
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import require_channel, require_role

logger = logging.getLogger(__name__)


trick_or_treat = TrickOrTreatHandler()


@require_channel([CONFIG.TRICK_OR_TREAT_CHANNEL_ID])
@require_role(ROLES.ANY)
async def cmd_trick_or_treat(interaction: discord.Interaction):
    return await trick_or_treat.random_result(interaction)
