import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.commands.spin.cmd_spin import MINIMUM_SPIN_OPTIONS
from ironforgedcore.common.normalize import normalize_discord_string
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


def _default_next_monday_str() -> str:
    """Return today UTC as `YYYY-MM-DD`, snapped to the next Monday.

    If today is already Monday, returns today.
    """
    today_utc = datetime.now(timezone.utc).date()
    days_ahead = (0 - today_utc.weekday()) % 7
    default_start = today_utc + timedelta(days=days_ahead)
    return default_start.strftime("%Y-%m-%d")


class SpinOptionsModal(discord.ui.Modal):
    """Modal for spinning with editable option list."""

    def __init__(
        self,
        title: str,
        base_options: list[str],
        on_result: Callable[
            [discord.Interaction, discord.File, str, int, int, list[str]],
            Awaitable[None],
        ],
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

        self.start_date_input = discord.ui.TextInput(
            label="Start date (YYYY-MM-DD, UTC)",
            placeholder="YYYY-MM-DD",
            required=True,
            max_length=10,
            style=discord.TextStyle.short,
            default=_default_next_monday_str(),
        )
        self.add_item(self.start_date_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        options = [
            normalize_discord_string(o.strip())
            for o in self.options_input.value.split(",")
            if o.strip()
        ]
        options = [o for o in options if o]

        if len(options) < MINIMUM_SPIN_OPTIONS:
            await send_error_response(
                interaction,
                f"At least {MINIMUM_SPIN_OPTIONS} options are required to spin.",
            )
            return

        raw_date = self.start_date_input.value.strip()
        try:
            start_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            end_date = start_date + timedelta(days=7)
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())
        except ValueError:
            await send_error_response(
                interaction,
                f"`{raw_date}` is not a valid date. Use `YYYY-MM-DD`.",
            )
            return

        generating_msg = await interaction.followup.send(
            "Generating GIF...",
            ephemeral=True,
            wait=True,
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

        await self.on_result(interaction, file, winner, start_ts, end_ts, options)

        try:
            await generating_msg.delete()
        except discord.HTTPException:
            pass
