import functools
import logging
import time

import discord

from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


def rate_limit(rate: int = 1, seconds: int = 3600):
    """Limits how often a command can be called by an individual user"""

    from ironforgedbot.common.responses import send_error_response

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> None:
            interaction = args[0]
            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as first argument ({func.__name__})"
                )

            if not interaction.command:
                raise ValueError(
                    f"Interaction command is None, cannot apply rate limit ({func.__name__})"
                )

            command_name = interaction.command.name
            user_id = str(interaction.user.id)
            now = time.time()

            if command_name not in STATE.state["rate_limit"]:
                STATE.state["rate_limit"][command_name] = {}

            command_limits = STATE.state["rate_limit"][command_name]

            if user_id not in command_limits:
                command_limits[user_id] = []

            timestamps = command_limits[user_id]
            timestamps = [t for t in timestamps if now - t < seconds]
            command_limits[user_id] = timestamps

            if len(timestamps) >= rate:
                if not interaction.response.is_done():
                    await interaction.response.defer(thinking=True, ephemeral=True)

                retry_after = seconds - (now - timestamps[0])
                mins = int(retry_after // 60)
                secs = int(retry_after % 60)

                logger.debug(
                    f"Rate limit hit: {interaction.user.display_name} for {func.__name__} "
                    f"({mins}m {secs}s remaining)"
                )

                message = (
                    "**Woah, tiger.** You are using this command too quickly.\n\n"
                    f"Try again in **{mins}** minutes and **{secs}** seconds."
                )
                return await send_error_response(
                    interaction, message, report_to_channel=False
                )

            timestamps.append(now)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
