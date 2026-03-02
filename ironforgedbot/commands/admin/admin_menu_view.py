import logging
from typing import Optional

import discord
from discord.ui import View

from ironforgedbot.commands.admin.check_activity import cmd_check_activity
from ironforgedbot.commands.admin.check_discrepancies import cmd_check_discrepancies
from ironforgedbot.commands.admin.process_absentees import cmd_process_absentees
from ironforgedbot.commands.admin.refresh_ranks import cmd_refresh_ranks
from ironforgedbot.commands.admin.spin_members_view import SpinMembersView
from ironforgedbot.commands.admin.spin_options_modal import SpinOptionsModal
from ironforgedbot.commands.admin.sync_members import cmd_sync_members
from ironforgedbot.commands.admin.view_logs import cmd_view_logs
from ironforgedbot.commands.admin.view_state import cmd_view_state
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.storage.data import BOSSES, SKILLS

logger = logging.getLogger(__name__)


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

        async def on_result(interaction, file, winner):
            skill = next((s for s in SKILLS if s["name"] == winner), None)
            emoji = find_emoji(skill["emoji_key"]) if skill else ""
            msg = await interaction.channel.send(
                file=file,
                content=f"-# spinning skill of the week...\n# {emoji} {winner}",
            )
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")

        await interaction.response.send_modal(SpinOptionsModal("Spin SOTW", options, on_result))

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
        options = [b["name"] for b in BOSSES if b["name"].lower() not in exclusions]

        async def on_result(interaction, file, winner):
            boss = next((b for b in BOSSES if b["name"] == winner), None)
            emoji = find_emoji(boss["emoji_key"]) if boss else ""
            msg = await interaction.channel.send(
                file=file,
                content=f"-# spinning boss of the week...\n# {emoji} {winner}",
            )
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")

        await interaction.response.send_modal(SpinOptionsModal("Spin BOTW", options, on_result))

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

        async def on_result(interaction, file, winner):
            await interaction.channel.send(
                file=file, content=f"-# spinning...\n# {winner}"
            )

        await interaction.response.send_modal(SpinOptionsModal("Spin Custom", [], on_result))

    @discord.ui.button(
        label="Spin Members",
        style=discord.ButtonStyle.grey,
        custom_id="spin_members",
        emoji="👥",
        row=3,
    )
    async def spin_members_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.clear_parent()
        view = SpinMembersView()
        await interaction.response.send_message(
            "Select a role to spin members from:", view=view, ephemeral=True
        )
        view.message = await interaction.original_response()
