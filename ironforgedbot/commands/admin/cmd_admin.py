import logging

import discord

from ironforgedbot.commands.admin.admin_menu_view import AdminMenuView
from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)


@require_role(ROLE.LEADERSHIP, ephemeral=True)
@log_command_execution(logger)
async def cmd_admin(interaction: discord.Interaction):
    """Allows access to various administrative commands.

    Arguments:
        interaction: Discord Interaction from CommandTree.
    """
    report_channel = get_text_channel(interaction.guild, CONFIG.AUTOMATION_CHANNEL_ID)
    if not report_channel:
        logger.error("Error finding report channel for cmd_admin")
        return await send_error_response(interaction, "Error accessing report channel.")

    menu = AdminMenuView(report_channel=report_channel)
    menu.message = await interaction.followup.send(
        content="## 🤓 Administration Menu", view=menu, ephemeral=True
    )
