import asyncio
import functools
import logging
from pprint import pformat
from random import randrange

import discord

from ironforgedbot.common.responses import send_error_response
from ironforgedbot.state import state
from ironforgedbot.common.helpers import validate_member_has_role
from ironforgedbot.common.roles import ROLES

logger = logging.getLogger(__name__)


def require_role(role_name: str, ephemeral=False):
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

            if state.is_shutting_down:
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

            if role_name != ROLES.ANY:
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
