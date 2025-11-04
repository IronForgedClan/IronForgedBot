import functools
import json
import logging
import random
import time

import discord

from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)
COMMAND_PRICE_DATA_FILE = "data/command_price.json"


def _load_flavor_text(file_path: str = COMMAND_PRICE_DATA_FILE) -> list[str]:
    """Load and parse the command price flavor text JSON file.

    Args:
        file_path: Path to the JSON file. Defaults to COMMAND_PRICE_DATA_FILE.

    Returns:
        List of flavor text strings.

    Raises:
        FileNotFoundError: If the data file doesn't exist.
        ValueError: If the JSON syntax is invalid.
        KeyError: If the required 'flavor_text' key is missing.
        RuntimeError: For unexpected errors during loading.
    """
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Command price data file not found: {e.filename}. "
            f"Expected file at: {file_path}"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON syntax in command price data file: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error loading command price data: {e}") from e

    if "flavor_text" not in data:
        raise KeyError(f"Missing required key 'flavor_text' in data file: {file_path}")

    return data["flavor_text"]


FLAVOR_TEXT_OPTIONS = _load_flavor_text()


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

            async with db.get_session() as session:
                member_service = MemberService(session)
                member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )
                current_balance = member.ingots if member else 0

            ingot_icon = find_emoji("Ingot")

            expire_timestamp = int(time.time() + 30)
            expires_formatted = f"<t:{expire_timestamp}:R>"

            try:
                flavor_text = f"*{random.choice(FLAVOR_TEXT_OPTIONS)}*\n"
            except Exception as e:
                logger.error(e)
                flavor_text = ""

            embed = build_response_embed(
                title="💰 Command Price",
                description=flavor_text,
                color=discord.Colour.gold(),
            )
            embed.set_thumbnail(
                url="https://oldschool.runescape.wiki/images/thumb/Coins_detail.png/120px-Coins_detail.png"
            )
            embed.add_field(
                name="Your Balance",
                value=f"{ingot_icon} {current_balance:,}",
                inline=True,
            )
            embed.add_field(
                name="Price",
                value=f"{ingot_icon} {amount:,}",
                inline=True,
            )
            embed.add_field(
                name="",
                value=f"-# This interaction expires {expires_formatted}.",
                inline=False,
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
