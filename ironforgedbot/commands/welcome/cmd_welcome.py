import logging

import discord

from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.welcome import send_welcome_messages
from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_welcome(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    failure_reason = None
    try:
        await send_welcome_messages(interaction.user)
    except discord.Forbidden as error:
        failure_reason = f"{type(error).__name__}: {error}"
        response = "Unable to DM welcome messages. Check that your DMs are open."
    except Exception as error:
        failure_reason = f"{type(error).__name__}: {error}"
        logger.exception(f"Unable to send welcome messages to {interaction.user}")
        response = "Unable to send welcome messages. Contact a server administrator."
    else:
        response = "Welcome messages sent to your DMs."

    await _report_welcome_result(interaction, failure_reason)
    await interaction.followup.send(response, ephemeral=True)


async def _report_welcome_result(
    interaction: discord.Interaction, failure_reason: str | None
) -> None:
    try:
        report_channel = get_text_channel(
            interaction.guild, CONFIG.AUTOMATION_CHANNEL_ID
        )
        if not report_channel:
            logger.error(
                "Unable to report welcome command: automation channel not found"
            )
            return

        if failure_reason:
            report = (
                f"❌ Unable to send welcome messages to {interaction.user.mention} "
                f"(`{interaction.user.id}`).\nReason: {failure_reason[:500]}"
            )
        else:
            report = (
                f"✅ Welcome messages sent to {interaction.user.mention} "
                f"(`{interaction.user.id}`)."
            )

        await report_channel.send(
            report, allowed_mentions=discord.AllowedMentions.none()
        )
    except Exception:
        logger.exception("Unable to report welcome command result")
