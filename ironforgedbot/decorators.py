import functools
import logging

import discord

from ironforgedbot.common.helpers import validate_member_has_role

logger = logging.getLogger(__name__)


def require_role(role_name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if role_name is None:
                raise ValueError(f"No role provided to decorator ({func.__name__})")

            interaction = args[0]
            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as a first argument for '{func.__name__}'"
                )

            if not interaction.guild:
                raise ValueError("Unable to access guild information")

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                raise ValueError("Unable to access caller's guild membership")

            has_role = validate_member_has_role(member, role_name)
            if not has_role:
                raise discord.app_commands.CheckFailure(
                    f"Member '{interaction.user.display_name}' tried using {func.__name__} but does not have permission"
                )

            await func(*args, **kwargs)

        return wrapper

    return decorator
