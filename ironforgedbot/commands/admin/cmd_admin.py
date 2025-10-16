import logging
from typing import Optional

import discord
from discord.ui import View

from ironforgedbot.commands.admin.check_activity import cmd_check_activity
from ironforgedbot.commands.admin.check_discrepancies import cmd_check_discrepancies
from ironforgedbot.commands.admin.process_absentees import cmd_process_absentees
from ironforgedbot.commands.admin.refresh_ranks import cmd_refresh_ranks
from ironforgedbot.commands.admin.sync_members import cmd_sync_members
from ironforgedbot.commands.admin.view_logs import cmd_view_logs
from ironforgedbot.commands.admin.view_state import cmd_view_state
from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators.decorators import require_role

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
        emoji="🔁",
        row=0,
    )
    async def member_sync_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()
        await cmd_sync_members(interaction, self.report_channel)

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
        await self.clear_parent()
        await cmd_check_discrepancies(interaction, self.report_channel)

    @discord.ui.button(
        label="Member Activity Check",
        style=discord.ButtonStyle.grey,
        custom_id="activity_check",
        emoji="🧗",
        row=0,
    )
    async def member_activity_check_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()
        await cmd_check_activity(interaction, self.report_channel)

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
        await self.clear_parent()
        await cmd_refresh_ranks(interaction, self.report_channel)

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
        await self.clear_parent()
        await cmd_view_logs(interaction)

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
        await self.clear_parent()
        await cmd_view_state(interaction)

    @discord.ui.button(
        label="Process Absentee List",
        style=discord.ButtonStyle.grey,
        custom_id="absentee_list",
        emoji="🚿",
        row=0,
    )
    async def process_absentee_list_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()
        await cmd_process_absentees(interaction)
