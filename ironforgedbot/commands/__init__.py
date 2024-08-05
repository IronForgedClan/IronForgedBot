import logging

import discord
from decorator import decorator

from ironforgedbot.common.helpers import validate_member_has_role
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


@decorator
async def protected_command(func, role=None, *args, **kwargs):
    if role is None:
        logger.error(f"No role specified for /{func.__name__}")
        return

    interaction = args[0]
    if not isinstance(interaction, discord.Interaction):
        logger.error(f"Expected to see interaction as a first argument for /{func.__name__}")
        return

    logger.info(f"Handling '/{func.__name__}: {args}' on behalf of {interaction.user.display_name}")

    await interaction.response.defer(thinking=True)

    member = interaction.guild.get_member(interaction.user.id)
    has_role = validate_member_has_role(member, role)

    if not has_role:
        logger.info(f"Member '{interaction.user.display_name}' "
                    f"tried using /{func.__name__} but does not have permission")

        await send_error_response(interaction,
                                  f"Member '{member.display_name}' does not have permission for this action")
        return

    try:
        await func(*args, **kwargs)
    except Exception as error:
        logger.error(f"Error handling '/{func.__name__}': {error}")
        raise
