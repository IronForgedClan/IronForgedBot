import json
import logging
import time

import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed

logger = logging.getLogger(__name__)

COMMAND_PRICE_DATA_FILE = "data/command_price.json"
COINS_THUMBNAIL_URL = (
    "https://oldschool.runescape.wiki/images/thumb/"
    "Coins_detail.png/120px-Coins_detail.png"
)
DEFAULT_PAYMENT_TITLE = "\U0001f4b0 Command Price"
DEFAULT_EXPIRATION_SECONDS = 30


def load_flavor_text(file_path: str = COMMAND_PRICE_DATA_FILE) -> list[str]:
    """Load and parse the command price flavor text JSON file.

    Args:
        file_path: Path to the JSON file. Defaults to COMMAND_PRICE_DATA_FILE.

    Returns:
        List of flavor text strings.

    Raises:
        FileNotFoundError: If the data file doesn't found.
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


def build_payment_embed(
    *,
    cost: int,
    user_balance: int,
    flavor_text: str = "",
    title: str = DEFAULT_PAYMENT_TITLE,
    thumbnail_url: str = COINS_THUMBNAIL_URL,
    expiration_seconds: int = DEFAULT_EXPIRATION_SECONDS,
) -> discord.Embed:
    """Build the canonical payment confirmation embed.

    Used by `command_price` decorator and any other flow that asks a user
    to confirm an ingot cost. Displays the user's current balance, the
    price being charged, and a Discord relative timestamp for when the
    confirmation expires.
    """
    ingot_icon = find_emoji("Ingot")
    expire_timestamp = int(time.time() + expiration_seconds)
    expires_formatted = f"<t:{expire_timestamp}:R>"

    embed = build_response_embed(
        title=title,
        description=flavor_text,
        color=discord.Colour.gold(),
    )
    embed.set_thumbnail(url=thumbnail_url)
    embed.add_field(
        name="Your Balance",
        value=f"{ingot_icon} {user_balance:,}",
        inline=True,
    )
    embed.add_field(
        name="Price",
        value=f"{ingot_icon} {cost:,}",
        inline=True,
    )
    embed.add_field(
        name="",
        value=f"-# This interaction expires {expires_formatted}.",
        inline=False,
    )
    return embed
