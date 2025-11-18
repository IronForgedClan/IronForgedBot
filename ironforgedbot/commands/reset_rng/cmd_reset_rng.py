import asyncio
import json
import logging
import random

import discord

from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.command_price import command_price
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)
RESET_RNG_DATA_FILE = "data/reset_rng.json"


def _load_reset_rng_data(file_path: str = RESET_RNG_DATA_FILE) -> dict:
    """Load and parse the reset RNG messages JSON file.

    Args:
        file_path: Path to the JSON file. Defaults to RESET_RNG_DATA_FILE.

    Returns:
        Dictionary containing message data.

    Raises:
        FileNotFoundError: If the data file doesn't exist.
        ValueError: If the JSON syntax is invalid.
        KeyError: If required keys are missing.
        RuntimeError: For unexpected errors during loading.
    """
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Reset RNG data file not found: {e.filename}. "
            f"Expected file at: {file_path}"
        ) from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON syntax in reset RNG data file: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error loading reset RNG data: {e}") from e

    required_keys = [
        "dice_rolling",
        "success",
        "failure",
        "success_thumbnail_urls",
        "failure_thumbnail_urls",
        "dice_thumbnail_url",
    ]
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise KeyError(
            f"Missing required keys in data file: {missing_keys}. File: {file_path}"
        )

    return data


@require_role(ROLE.MEMBER)
@command_price(999)
@log_command_execution(logger)
async def cmd_reset_rng(interaction: discord.Interaction):
    """Reset your RNG with a 50/50 success rate.

    Arguments:
        interaction: Discord Interaction from CommandTree.
    """
    try:
        data = _load_reset_rng_data()
    except Exception as e:
        logger.error(f"Failed to load reset RNG data: {e}")
        return await send_error_response(
            interaction,
            "An error occurred after payment was taken. Please contact staff for a refund, sorry!",
        )

    is_lucky = random.random() < 0.5

    dice_message_data = random.choice(data["dice_rolling"])

    dice_embed = build_response_embed(
        title=dice_message_data["title"],
        description=dice_message_data["description"],
        color=discord.Colour.from_rgb(255, 255, 255),
    )

    dice_embed.set_thumbnail(url=data["dice_thumbnail_url"])

    message = await interaction.followup.send(embed=dice_embed)

    await asyncio.sleep(7)

    result_data = random.choice(data["success"] if is_lucky else data["failure"])
    thumbnail_url = random.choice(
        data["success_thumbnail_urls"] if is_lucky else data["failure_thumbnail_urls"]
    )

    result_embed = build_response_embed(
        title=result_data["title"],
        description=result_data["description"],
        color=discord.Colour.green() if is_lucky else discord.Colour.red(),
    )
    result_embed.set_thumbnail(url=thumbnail_url)

    await message.edit(embed=result_embed)
