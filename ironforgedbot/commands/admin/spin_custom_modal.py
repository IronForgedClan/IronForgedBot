import logging

import discord

from ironforgedbot.commands.spin.build_spin_webm import build_spin_gif_file
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


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
