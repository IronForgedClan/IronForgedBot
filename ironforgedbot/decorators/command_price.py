import functools

import discord


def command_price(amount: int, ephemeral: bool = True):
    """Charges ingots before executing command. Shows confirmation prompt.

    This decorator works alongside @require_role by passing the button interaction down the chain.

    Args:
        amount: Number of ingots to charge
        ephemeral: Whether confirmation prompt is ephemeral (default: True)

    Usage:
        @command_price(100)
        @require_role(ROLE.MEMBER)
        @log_command_execution(logger)
        async def cmd_rng_reset(interaction):
            ...

    IMPORTANT: Must be the OUTERMOST decorator (listed first).
    """
    from ironforgedbot.common.helpers import find_emoji
    from ironforgedbot.common.responses import build_response_embed
    from ironforgedbot.decorators.views.ingot_cost_confirmation_view import (
        IngotCostConfirmationView,
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
                title="💰 Command Cost",
                description=f"This command costs {ingot_icon} **{amount:,}** ingots to use.\n\nDo you want to continue?",
                color=discord.Colour.gold(),
            )

            view = IngotCostConfirmationView(
                cost=amount,
                wrapped_function=func,
                original_args=args,
                original_kwargs=kwargs,
                command_name=func.__name__,
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=ephemeral
            )

        return wrapper

    return decorator
