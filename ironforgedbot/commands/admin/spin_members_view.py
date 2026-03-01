import logging
from typing import Optional

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


class SpinMembersView(discord.ui.View):
    """Ephemeral view with a RoleSelect dropdown to pick members for a spin."""

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
        members = [m.display_name for m in role.members if not m.bot]

        if len(members) < 2:
            await send_error_response(
                interaction,
                f"The role **{role.name}** has fewer than 2 members to spin.",
            )
            return

        if self.message:
            await self.message.delete()
            self.message = None

        try:
            file, winner = await build_spin_gif_file(members)
        except Exception as e:
            logger.error(f"Error generating spin GIF: {e}")
            await send_error_response(
                interaction, "Failed to generate spin animation. Please try again later."
            )
            return

        await interaction.channel.send(file=file, content=f"## {winner}")
