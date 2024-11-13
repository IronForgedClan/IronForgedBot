import asyncio
import functools
import logging
import time
from pprint import pformat
from random import randrange

import discord

from ironforgedbot.common.helpers import validate_member_has_role
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


def require_role(role_name: str, ephemeral=False):
    """Makes sure that the interaction user has the required role"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if role_name is None or len(role_name) < 1:
                raise ValueError(f"No role provided to decorator ({func.__name__})")

            interaction = args[0]
            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as first argument ({func.__name__})"
                )

            if not interaction.guild:
                raise ValueError(
                    f"Unable to access guild information ({func.__name__})"
                )

            logger.info(
                f"Handling '/{func.__name__}: {pformat(kwargs)}' on behalf of {interaction.user.display_name}"
            )

            if STATE.state["is_shutting_down"]:
                logger.warning("Bot has begun shut down. Ignoring command.")
                await interaction.response.send_message(
                    "## Bad Timing!!\nThe bot is shutting down, please try again when the bot comes back online."
                )
                return

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                raise ValueError(
                    f"Unable to verify caller's guild membership ({func.__name__})"
                )

            if role_name != ROLE.ANY:
                has_role = validate_member_has_role(member, role_name)
                if not has_role:
                    raise discord.app_commands.CheckFailure(
                        f"Member '{interaction.user.display_name}' tried using "
                        f"{func.__name__} but does not have permission"
                    )

            await interaction.response.defer(thinking=True, ephemeral=ephemeral)
            await func(*args, **kwargs)

        return wrapper

    return decorator


def require_channel(channel_ids: list[int]):
    """Makes sure that the interaction is happening in a whitelisted channel"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            interaction = args[0]
            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as first argument ({func.__name__})"
                )

            if interaction.channel_id not in channel_ids:
                logger.info(
                    f"Member '{interaction.user.display_name}' tried to use '{func.__name__}' "
                    f"in an invalid channel '{interaction.channel_id}'"
                )
                await interaction.response.defer(thinking=True, ephemeral=True)

                message = (
                    "Command cannot be used in this channel.\n\n**Supported channels:**"
                )
                for channel in channel_ids:
                    message += f"\n- <#{channel}>"

                return await send_error_response(interaction, message)

            await func(*args, **kwargs)

        return wrapper

    return decorator


def retry_on_exception(retries=3):
    """Retries function upon any exception up to retry limit"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < retries - 1:
                        sleep_time = randrange(1, 7)
                        logger.warning(
                            f"Fail #{attempt + 1} for {func.__name__}, "
                            f"retrying after {sleep_time}s sleep..."
                        )
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.critical(e)
                        raise e

        return wrapper

    return decorator


def rate_limit(rate: int = 1, seconds: int = 3600):
    """Limits how often a command can be called by an individual user"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            interaction = args[0]
            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as first argument ({func.__name__})"
                )

            assert interaction.command
            command_name = interaction.command.name
            user_id = str(
                interaction.user.id
            )  # when serializing state to json keys are strings
            now = time.time()

            # make sure we have a dict for this command
            if command_name not in STATE.state["rate_limit"]:
                STATE.state["rate_limit"][command_name] = {}

            command_limits = STATE.state["rate_limit"][command_name]

            # make sure we have an array for this user id
            if user_id not in command_limits:
                command_limits[user_id] = []

            # remove timestamps older than the cooldown period
            timestamps = command_limits[user_id]
            timestamps = [t for t in timestamps if now - t < seconds]
            command_limits[user_id] = timestamps

            if len(timestamps) >= rate:
                await interaction.response.defer(thinking=True, ephemeral=True)
                retry_after = seconds - (now - timestamps[0])
                mins = int(retry_after // 60)
                secs = int(retry_after % 60)

                logger.info(
                    f"Member '{interaction.user.display_name}' tried to use a rate limited command "
                    f"'{func.__name__}'. {mins}m and {secs}s remaining on cooldown."
                )

                message = (
                    "**Woah, tiger.** You are using this command too quickly.\n\n"
                    f"Try again in **{mins}** minutes and **{secs}** seconds."
                )
                return await send_error_response(interaction, message)

            timestamps.append(now)

            command_limits[user_id] = timestamps
            STATE.state["rate_limit"][command_name] = command_limits

            await func(*args, **kwargs)

        return wrapper

    return decorator


def singleton(cls):
    """A threadsafe singleton implementation"""
    instances = {}
    lock = asyncio.Lock()

    async def get_instance(*args, **kwargs):
        async with lock:
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
            return instances[cls]

    async def async_new(*args, **kwargs):
        return await get_instance(*args, **kwargs)

    class Wrapper:
        def __new__(cls, *args, **kwargs):
            return async_new(*args, **kwargs)

    return Wrapper
