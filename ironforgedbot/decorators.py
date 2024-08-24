import functools
import logging

import discord

from ironforgedbot.common.helpers import validate_member_has_role

logger = logging.getLogger(__name__)


def require_role(role_name: str):
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

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                raise ValueError(
                    f"Unable to verify caller's guild membership ({func.__name__})"
                )

            has_role = validate_member_has_role(member, role_name)
            if not has_role:
                raise discord.app_commands.CheckFailure(
                    f"Member '{interaction.user.display_name}' tried using {func.__name__} but does not have permission"
                )

            await func(*args, **kwargs)

        return wrapper

    return decorator
