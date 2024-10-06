import logging
import discord

from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role


logger = logging.getLogger(__name__)


@require_role(ROLES.ANY)
async def cmd_trick_or_treat(interaction: discord.Interaction):
    logger.info("trick")
