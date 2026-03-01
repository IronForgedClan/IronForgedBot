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
from ironforgedbot.commands.spin.build_spin_webm import build_spin_gif_file
from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.storage.data import BOSSES, SKILLS

logger = logging.getLogger(__name__)


class SpinOptionsModal(discord.ui.Modal):
    """Modal for SOTW/BOTW spins — allows admins to add or exclude options."""

    def __init__(self, title: str, base_options: list[str]):
        super().__init__(title=title)
        self._base_options = base_options

        self.additions = discord.ui.TextInput(
            label="Additions (comma-separated, optional)",
            required=False,
            style=discord.TextStyle.short,
        )
        self.exclusions = discord.ui.TextInput(
            label="Exclusions (comma-separated, optional)",
            required=False,
            style=discord.TextStyle.short,
        )
        self.add_item(self.additions)
        self.add_item(self.exclusions)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        additions = [o.strip() for o in self.additions.value.split(",") if o.strip()]
        exclusions_lower = {
            o.strip().lower() for o in self.exclusions.value.split(",") if o.strip()
        }

        options = [
            o for o in self._base_options if o.lower() not in exclusions_lower
        ] + additions

        if len(options) < 2:
            await send_error_response(
                interaction, "At least 2 options are required to spin."
            )
            return

        try:
            file, winner = await build_spin_gif_file(options)
        except Exception as e:
            logger.error(f"Error generating spin GIF: {e}")
            await send_error_response(
                interaction,
                "Failed to generate spin animation. Please try again later.",
            )
            return

        await interaction.channel.send(file=file, content=f"## {winner}")


class SpinCustomModal(discord.ui.Modal):
    """Modal for a fully custom spin with admin-supplied options."""

    def __init__(self):
        super().__init__(title="Spin Custom")

        self.options_input = discord.ui.TextInput(
            label="Options (comma-separated, min 2 required)",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        options = [o.strip() for o in self.options_input.value.split(",") if o.strip()]

        if len(options) < 2:
            await send_error_response(
                interaction,
                "Please provide at least 2 comma-separated options to spin.",
            )
            return

        try:
            file, winner = await build_spin_gif_file(options)
        except Exception as e:
            logger.error(f"Error generating spin GIF: {e}")
            await send_error_response(
                interaction,
                "Failed to generate spin animation. Please try again later.",
            )
            return

        await interaction.channel.send(file=file, content=f"## {winner}")


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

    @discord.ui.button(
        label="Spin SOTW",
        style=discord.ButtonStyle.grey,
        custom_id="spin_sotw",
        emoji="🌀",
        row=3,
    )
    async def spin_sotw_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()

        exclusions = ["attack", "strength", "defence", "hitpoints", "ranged", "prayer"]
        options = [s["name"] for s in SKILLS if s["name"].lower() not in exclusions]

        await interaction.response.send_modal(SpinOptionsModal("Spin SOTW", options))

    @discord.ui.button(
        label="Spin BOTW",
        style=discord.ButtonStyle.grey,
        custom_id="spin_botw",
        emoji="🌀",
        row=3,
    )
    async def spin_botw_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()

        exclusions = ["rifts closed"]
        options = [b["name"] for b in BOSSES if b["name"] not in exclusions]

        await interaction.response.send_modal(SpinOptionsModal("Spin BOTW", options))

    @discord.ui.button(
        label="Spin Custom",
        style=discord.ButtonStyle.grey,
        custom_id="spin_custom",
        emoji="🎲",
        row=3,
    )
    async def spin_custom_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()
        await interaction.response.send_modal(SpinCustomModal())
