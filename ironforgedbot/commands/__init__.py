import logging

import discord
from decorator import decorator

from ironforgedbot.common.helpers import validate_protected_request
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


@decorator
async def protected_command(func, role=None, *args, **kwargs):
    if role is None:
        logger.error("No role specified")
        return

    interaction = args[0]
    if not isinstance(interaction, discord.Interaction):
        logger.error("Expected top see interaction as a first argument")
        return

    logger.info(
            f"Handling '/{func.__name__} :{args}' on behalf of {interaction.user.display_name}"
    )

    await interaction.response.defer()
    try:
        validate_protected_request(
                interaction, interaction.user.display_name, role
        )
    except (ReferenceError, ValueError) as error:
        logger.info(
                f"Member '{interaction.user.display_name}' tried using roster but does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    await func(*args, **kwargs)
