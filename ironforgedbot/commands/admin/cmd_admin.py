import logging
from typing import Optional

import discord
from discord.ui import View

from ironforgedbot.commands.admin.internal_state import get_internal_state
from ironforgedbot.commands.admin.latest_log import get_latest_log_file
from ironforgedbot.common.helpers import (
    get_text_channel,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import require_role
from ironforgedbot.tasks.job_check_activity import job_check_activity
from ironforgedbot.tasks.job_membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks
from ironforgedbot.tasks.job_sync_members import job_sync_members

logger = logging.getLogger(__name__)


@require_role(ROLE.LEADERSHIP, ephemeral=True)
async def cmd_admin(interaction: discord.Interaction):
    """Allows access to various administrative commands.

    Arguments:
        interaction: Discord Interaction from CommandTree.
    """
    report_channel = get_text_channel(interaction.guild, CONFIG.AUTOMATION_CHANNEL_ID)
    if not report_channel:
        logger.error("Error finding report channel for cmd_activity_check")
        return await send_error_response(interaction, "Error accessing report channel.")

    menu = AdminMenuView(report_channel=report_channel)
    menu.message = await interaction.followup.send(
        content="## 🤓 Administration Menu", view=menu
    )


class AdminMenuView(View):
    def __init__(
        self, *, report_channel: discord.TextChannel, timeout: Optional[float] = 180
    ):
        self.report_channel = report_channel
        self.message: Optional[discord.Message] = None

        super().__init__(timeout=timeout)

    async def on_timeout(self) -> None:
        await self.clear_parent()

        return await super().on_timeout()

    async def clear_parent(self):
        if self.message:
            self.message = await self.message.delete()

    @discord.ui.button(
        label="Sync Members",
        style=discord.ButtonStyle.grey,
        custom_id="sync_members",
        emoji="🤖",
        row=0,
    )
    async def member_sync_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        assert interaction.guild
        await interaction.response.send_message(
            "## Manually initiating member sync job...\n"
            f"View <#{self.report_channel.id}> for output.",
            ephemeral=True,
        )

        await self.clear_parent()
        logger.info("Manually initiating sync member job")

        await job_sync_members(interaction.guild, self.report_channel)

    @discord.ui.button(
        label="Member Discrepancy Check",
        style=discord.ButtonStyle.grey,
        custom_id="discrepancy_check",
        emoji="🤖",
        row=0,
    )
    async def member_discrepancy_check_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        assert interaction.guild
        await interaction.response.send_message(
            "## Manually initiating member discrepancy job...\n"
            f"View <#{self.report_channel.id}> for output.",
            ephemeral=True,
        )

        await self.clear_parent()
        logger.info("Manually initiating member discrepancy job")

        await job_check_membership_discrepancies(
            interaction.guild,
            self.report_channel,
            CONFIG.WOM_API_KEY,
            CONFIG.WOM_GROUP_ID,
        )

    @discord.ui.button(
        label="Member Activity Check",
        style=discord.ButtonStyle.grey,
        custom_id="activity_check",
        emoji="🤖",
        row=0,
    )
    async def member_activity_check_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "## Manually initiating activity check job...\n"
            f"View <#{self.report_channel.id}> for output.",
            ephemeral=True,
        )

        await self.clear_parent()
        logger.info("Manually initiating activity check job")

        await job_check_activity(
            self.report_channel, CONFIG.WOM_API_KEY, CONFIG.WOM_GROUP_ID
        )

    @discord.ui.button(
        label="Member Rank Check",
        style=discord.ButtonStyle.grey,
        custom_id="rank_check",
        emoji="🤖",
        row=0,
    )
    async def member_rank_check_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        assert interaction.guild
        await interaction.response.send_message(
            "## Manually initiating rank check job...\n"
            f"View <#{self.report_channel.id}> for output.",
            ephemeral=True,
        )

        await self.clear_parent()
        logger.info("Manually initiating refresh ranks job")

        await job_refresh_ranks(interaction.guild, self.report_channel)

    @discord.ui.button(
        label="View Latest Log",
        style=discord.ButtonStyle.blurple,
        custom_id="view_logs",
        emoji="🗃️",
        row=1,
    )
    async def view_logs_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Sends the latest log file."""
        logger.info("Sending latest log file to user...")
        await self.clear_parent()
        await interaction.response.defer(thinking=True, ephemeral=True)

        file = get_latest_log_file()

        if not file:
            return await send_error_response(interaction, "Error processing log file.")

        return await interaction.followup.send(content="## Latest Log File", file=file)

    @discord.ui.button(
        label="View Internal State",
        style=discord.ButtonStyle.blurple,
        custom_id="view_state",
        emoji="🧠",
        row=1,
    )
    async def view_state_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Sends internal bot state."""
        logger.info("Sending internal state to user...")
        await self.clear_parent()
        await interaction.response.defer(thinking=True, ephemeral=True)

        file = get_internal_state()

        return await interaction.followup.send(
            content="## Current Internal State", file=file
        )
