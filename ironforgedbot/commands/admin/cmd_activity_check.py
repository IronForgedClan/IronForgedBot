import logging
import discord
from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import require_role
from ironforgedbot.tasks.check_activity import job_check_activity

logger = logging.getLogger(__name__)


@require_role(ROLE.LEADERSHIP, ephemeral=True)
async def cmd_activity_check(interaction: discord.Interaction):
    assert interaction.guild
    report_channel = get_text_channel(interaction.guild, CONFIG.AUTOMATION_CHANNEL_ID)

    if not report_channel:
        logger.error("Error finding report channel for cmd_activity_check")
        await send_error_response(interaction, "Error getting report channel.")
        return

    await interaction.followup.send(
        f"Manually initiating activity check job...\nView <#{report_channel.id}> for output."
    )
    await job_check_activity(report_channel, CONFIG.WOM_API_KEY, CONFIG.WOM_GROUP_ID)
