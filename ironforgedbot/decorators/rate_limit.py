import functools
import logging
import time

import discord

from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


def rate_limit(rate: int = 1, seconds: int = 3600):
    """Limits how often a command can be called by an individual user"""

    from ironforgedbot.common.responses import send_ephemeral_error

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
                retry_after = seconds - (now - timestamps[0])
                retry_timestamp = int(now + retry_after)

                logger.debug(
                    f"Rate limit hit: {interaction.user.display_name} for {func.__name__} "
                    f"(retry at {retry_timestamp})"
                )

                message = (
                    "**Woah, tiger.** You are using this command too quickly.\n\n"
                    f"Try again <t:{retry_timestamp}:R>."
                )
                return await send_ephemeral_error(interaction, message)

            timestamps.append(now)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
