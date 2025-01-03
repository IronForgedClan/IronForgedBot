import io
import json
import logging
import os
from typing import Optional

import discord
from discord.ui import View

from ironforgedbot.common.helpers import (
    get_text_channel,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import require_role
from ironforgedbot.logging_config import LOG_DIR
from ironforgedbot.state import STATE
from ironforgedbot.tasks.check_activity import job_check_activity
from ironforgedbot.tasks.job_sync_members import job_sync_members
from ironforgedbot.tasks.job_membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.refresh_ranks import job_refresh_ranks

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
        logger.info("Manually initiating refresh rankd job")

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

        try:
            files = [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR)]
            files = [f for f in files if os.path.isfile(f)]
            latest_file = max(files, key=os.path.getmtime)

            return await interaction.followup.send(
                content="## Latest Log File", file=discord.File(latest_file)
            )
        except Exception as e:
            logger.error(e)
            return await send_error_response(interaction, "Error processing log file.")

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

        json_bytes = io.BytesIO(json.dumps(STATE.state, indent=2).encode("utf-8"))
        json_bytes.seek(0)

        return await interaction.followup.send(
            content="## Current Internal State",
            file=discord.File(json_bytes, "state.json"),
        )
