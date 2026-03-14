import logging
from typing import Optional

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.commands.spin.cmd_spin import MINIMUM_SPIN_OPTIONS
from ironforgedbot.commands.spin.spin_result_handler import send_spin_result
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


class SpinMembersView(discord.ui.View):
    """Ephemeral view with a RoleSelect dropdown to pick members for spin."""

    def __init__(self):
        super().__init__(timeout=120)
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        if self.message:
            await self.message.delete()
        return await super().on_timeout()

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select a role to spin members from...",
        min_values=1,
        max_values=1,
    )
    async def role_select(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ):
        await interaction.response.defer(ephemeral=True)
        role = select.values[0]

        # Keep member objects, extract display names for GIF
        member_list = [m for m in role.members if not m.bot]
        display_names = [m.display_name for m in member_list]

        if len(display_names) < MINIMUM_SPIN_OPTIONS:
            await send_error_response(
                interaction,
                f"The role **{role.name}** has fewer than {MINIMUM_SPIN_OPTIONS} members to spin.",
            )
            return

        try:
            file, winner_display_name = await build_spin_gif_file(display_names)
        except Exception as e:
            logger.error(f"Error generating spin GIF: {e}")
            await send_error_response(
                interaction,
                "Failed to generate spin animation. Please try again later.",
            )
            return

        winning_member = next(
            (m for m in member_list if m.display_name == winner_display_name),
            None,
        )
        winner_mention = (
            winning_member.mention if winning_member else winner_display_name
        )

        if self.message:
            await self.message.delete()
            self.message = None

        await send_spin_result(
            interaction,
            file,
            winner_mention,
            spinning_text=f"_spinning everyone with the **{role.name}** role..._",
            winning_text="_and the winner is..._",
            emoji=None,
            use_padding=False,
            reactions=None,
        )
