import logging

import discord

from ironforgedbot.commands.spin.build_spin_webm import build_spin_gif_file
from ironforgedbot.common.responses import send_error_response

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
