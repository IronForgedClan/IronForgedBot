import functools
import logging
import random

import discord

from ironforgedcore.database import db
from ironforgedcore.services.member_service import MemberService
from ironforgedbot.common.payment_embed import build_payment_embed, load_flavor_text

logger = logging.getLogger(__name__)


def command_price(amount: int):
    """Charges ingots before executing command. Shows confirmation prompt.

    This decorator sends a separate channel message with confirmation buttons.
    The @require_role decorator should be applied first (outermost) to check permissions
    and defer the interaction, then @command_price sends the confirmation message.

    The confirmation message is sent to the channel (visible to everyone) but is deleted
    after the user responds. This keeps the original interaction clean so the command's
    response can replace the original "thinking" message.

    Args:
        amount: Number of ingots to charge

    Usage:
        @require_role(ROLE.MEMBER)
        @command_price(199)
        @log_command_execution(logger)
        async def cmd_do_something(interaction):
            # interaction is the original interaction from the command invocation
            ...
    """
    from ironforgedbot.decorators.views.command_price_confirmation_view import (
        CommandPriceConfirmationView,
    )

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            interaction = args[0]

            if not isinstance(interaction, discord.Interaction):
                raise ReferenceError(
                    f"Expected discord.Interaction as first argument ({func.__name__})"
                )

            async with db.get_session() as session:
                member_service = MemberService(session)
                member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )
                current_balance = member.ingots if member else 0

            try:
                flavor_text_options = load_flavor_text()
                flavor_text = f"*{random.choice(flavor_text_options)}*\n"
            except Exception as e:
                logger.error(e)
                flavor_text = ""

            embed = build_payment_embed(
                cost=amount,
                user_balance=current_balance,
                flavor_text=flavor_text,
            )

            view = CommandPriceConfirmationView(
                cost=amount,
                wrapped_function=func,
                original_args=args,
                original_kwargs=kwargs,
                command_name=func.__name__,
                user_id=interaction.user.id,
            )

            original_message = await interaction.original_response()
            confirmation_message = await interaction.channel.send(
                content=interaction.user.mention,
                embed=embed,
                view=view,
                reference=original_message,
            )

            view.confirmation_message = confirmation_message

        wrapper.ingot_cost = amount
        return wrapper

    return decorator
