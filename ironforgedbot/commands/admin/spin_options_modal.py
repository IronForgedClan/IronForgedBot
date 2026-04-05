import logging
from collections.abc import Awaitable, Callable

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.commands.spin.cmd_spin import MINIMUM_SPIN_OPTIONS
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


class SpinOptionsModal(discord.ui.Modal):
    """Modal for spinning with editable option list."""

    def __init__(
        self,
        title: str,
        base_options: list[str],
        on_result: Callable[[discord.Interaction, discord.File, str], Awaitable[None]],
    ):
        super().__init__(title=title)

        self.on_result = on_result

        self.options_input = discord.ui.TextInput(
            label="Options (comma-separated)",
            required=True,
            style=discord.TextStyle.paragraph,
            default=", ".join(base_options),
        )
        self.add_item(self.options_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        options = [o.strip() for o in self.options_input.value.split(",") if o.strip()]

        if len(options) < MINIMUM_SPIN_OPTIONS:
            await send_error_response(
                interaction,
                f"At least {MINIMUM_SPIN_OPTIONS} options are required to spin.",
            )
            return

        await interaction.followup.send(
            "_spinning..._",
            ephemeral=True,
        )

        try:
            file, winner = await build_spin_gif_file(options)
        except Exception as e:
            logger.error(f"Error generating spin GIF: {e}")
            await send_error_response(
                interaction,
                "Failed to generate spin animation. Please try again later.",
            )
            return

        await self.on_result(interaction, file, winner)
