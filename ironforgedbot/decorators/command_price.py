import functools

import discord


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
        @command_price(100)
        @log_command_execution(logger)
        async def cmd_rng_reset(interaction):
            # interaction is the original interaction from the command invocation
            ...
    """
    from ironforgedbot.common.helpers import find_emoji
    from ironforgedbot.common.responses import build_response_embed
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

            ingot_icon = find_emoji("Ingot")
            embed = build_response_embed(
                title=f"{ingot_icon} Command Price",
                description=f"This command costs {ingot_icon} **{amount:,}** ingots to use.\n\nDo you want to continue?",
                color=discord.Colour.gold(),
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

        return wrapper

    return decorator
