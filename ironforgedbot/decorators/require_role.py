import functools
import logging

import discord

from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


def require_role(role: ROLE):
    """Makes sure that the interaction user has the required role or higher"""

    from ironforgedbot.common.helpers import normalize_discord_string

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not role:
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

            if STATE.state["is_shutting_down"]:
                logger.warning("Bot has begun shut down. Ignoring command.")
                return await interaction.response.send_message(
                    (
                        "## Bad Timing!!\nThe bot is shutting down, "
                        "please try again when the bot comes back online."
                    )
                )

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                raise ValueError(
                    f"Unable to verify caller's guild membership ({func.__name__})"
                )

            if not check_member_has_role(member, role, or_higher=True):
                logger.warning(
                    f"Access denied: {interaction.user.display_name} tried {func.__name__} without {role} role"
                )
                raise discord.app_commands.CheckFailure(
                    f"Member '{normalize_discord_string(interaction.user.display_name)}' "
                    f"tried using '{func.__name__}' but does not have permission"
                )

            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
