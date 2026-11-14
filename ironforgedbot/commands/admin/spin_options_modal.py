import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.commands.spin.cmd_spin import MINIMUM_SPIN_OPTIONS
from ironforgedcore.common.normalize import normalize_discord_string
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


def _default_weekly_spin_dates() -> tuple[str, str]:
    today_utc = datetime.now(timezone.utc).date()
    days_ahead = (0 - today_utc.weekday()) % 7
    next_monday = today_utc + timedelta(days=days_ahead)
    start_date = datetime(
        next_monday.year,
        next_monday.month,
        next_monday.day,
        tzinfo=timezone.utc,
    )
    end_date = start_date + timedelta(days=7)
    date_format = "%Y-%m-%d %H:%M"
    return start_date.strftime(date_format), end_date.strftime(date_format)


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
        default_start_date, default_end_date = _default_weekly_spin_dates()

        self.options_input = discord.ui.TextInput(
            label="Options (comma-separated)",
            required=True,
            style=discord.TextStyle.paragraph,
            default=", ".join(base_options),
        )
        self.add_item(self.options_input)

        self.start_date_input = discord.ui.TextInput(
            label="Start date (YYYY-MM-DD HH:MM, UTC)",
            placeholder="YYYY-MM-DD HH:MM",
            required=True,
            max_length=16,
            style=discord.TextStyle.short,
            default=default_start_date,
        )
        self.add_item(self.start_date_input)

        self.end_date_input = discord.ui.TextInput(
            label="End date (YYYY-MM-DD HH:MM, UTC)",
            placeholder="YYYY-MM-DD HH:MM",
            required=True,
            max_length=16,
            style=discord.TextStyle.short,
            default=default_end_date,
        )
        self.add_item(self.end_date_input)

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

        if len({option.casefold() for option in options}) < 2:
            await send_error_response(
                interaction,
                "At least two distinct options are required to spin again.",
            )
            return

        raw_start_date = self.start_date_input.value.strip()
        raw_end_date = self.end_date_input.value.strip()
        date_format = "%Y-%m-%d %H:%M"
        try:
            start_date = datetime.strptime(raw_start_date, date_format).replace(
                tzinfo=timezone.utc
            )
            end_date = datetime.strptime(raw_end_date, date_format).replace(
                tzinfo=timezone.utc
            )
            if (
                start_date.strftime(date_format) != raw_start_date
                or end_date.strftime(date_format) != raw_end_date
            ):
                raise ValueError("Date format must be exact")
        except ValueError:
            await send_error_response(
                interaction,
                "Both dates must use `YYYY-MM-DD HH:MM` in UTC.",
            )
            return

        if end_date <= start_date:
            await send_error_response(interaction, "End date must be after start date.")
            return

        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        generating_msg = await interaction.followup.send(
            "Generating GIF...",
            ephemeral=True,
            wait=True,
        )

        try:
            try:
                file, winner = await build_spin_gif_file(options)
            except Exception:
                logger.exception("Error generating spin GIF")
                await self._send_failure_response(
                    interaction,
                    "Failed to generate spin animation. Please try again later.",
                )
                return

            try:
                await self.on_result(
                    interaction, file, winner, start_ts, end_ts, options
                )
            except Exception:
                logger.exception("Failed to post spin result")
                await self._send_failure_response(
                    interaction,
                    "Failed to post spin result. Check the channel before trying again.",
                )
        finally:
            try:
                await generating_msg.delete()
            except Exception as e:
                logger.warning(f"Failed to delete spin progress message: {e}")

    async def _send_failure_response(
        self, interaction: discord.Interaction, message: str
    ) -> None:
        try:
            await send_error_response(interaction, message)
        except Exception:
            logger.exception("Failed to send spin modal error response")
