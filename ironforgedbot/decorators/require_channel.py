import functools
import logging

import discord

logger = logging.getLogger(__name__)


def require_channel(channel_ids: list[int]):
    """Makes sure that the interaction is happening in a whitelisted channel"""

    from ironforgedbot.common.responses import send_ephemeral_error

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            interaction = args[0]
            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as first argument ({func.__name__})"
                )

            if interaction.channel_id not in channel_ids:
                logger.debug(
                    f"Channel restriction: {interaction.user.display_name} tried {func.__name__} "
                    f"in channel {interaction.channel_id}"
                )

                message = (
                    "Command cannot be used in this channel.\n\n**Supported channels:**"
                )
                for channel in channel_ids:
                    message += f"\n- <#{channel}>"

                return await send_ephemeral_error(interaction, message)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
