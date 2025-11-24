import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Any

import discord

from ironforgedbot.common.constants import MAX_EMBED_DESCRIPTION_LENGTH
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.command_price import command_price
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)

DATA_FILE = "data/eight_ball.json"


def _load_eight_ball_data(file_path: str = DATA_FILE) -> dict[str, Any]:
    """Load and parse the eight ball JSON file.

    Args:
        file_path: Path to the eight ball data JSON file.

    Returns:
        A dictionary containing the eight ball data.

    Raises:
        FileNotFoundError: If the data file doesn't exist.
        ValueError: If the JSON is malformed.
        KeyError: If required keys are missing.
        RuntimeError: For other unexpected errors.
    """
    try:
        data_path = Path(file_path)
        if not data_path.exists():
            raise FileNotFoundError(
                f"Eight ball data file not found at {file_path}. "
                f"Please ensure the file exists and the path is correct."
            )

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = ["loading_messages", "responses", "loading_thumbnail_url"]
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise KeyError(
                f"Missing required keys in eight ball data: {', '.join(missing_keys)}"
            )

        if not data["loading_messages"]:
            raise ValueError("loading_messages array is empty")
        if not data["responses"]:
            raise ValueError("responses array is empty")

        return data

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in eight ball data file: {e}") from e
    except (FileNotFoundError, KeyError, ValueError):
        raise
    except Exception as e:
        raise RuntimeError(f"Unexpected error loading eight ball data: {e}") from e


@require_role(ROLE.MEMBER)
@command_price(1999)
@log_command_execution(logger)
@discord.app_commands.describe(question="A yes or no question to ask the 8-ball.")
async def cmd_eight_ball(interaction: discord.Interaction, question: str) -> None:
    """Ask the Magic 8-Ball a question and receive mystical wisdom.

    Args:
        interaction: The Discord interaction object.
        question: The question to ask the Magic 8-Ball.
    """
    try:
        data = _load_eight_ball_data()

        loading_msg = random.choice(data["loading_messages"])

        loading_embed = build_response_embed(
            title=f"🎱 {loading_msg['title']}",
            description=loading_msg["description"],
            color=discord.Colour.from_rgb(255, 255, 255),
        )
        loading_embed.set_thumbnail(url=data["loading_thumbnail_url"])

        message = await interaction.followup.send(embed=loading_embed)

        await asyncio.sleep(7)

        response = random.choice(data["responses"])

        display_name = interaction.user.display_name
        eight_ball_response = response["title"]

        format_overhead = (
            len(display_name)
            + len("### asked:\n")
            + len("\n### 8-ball answered:\n")
            + len(eight_ball_response)
        )
        max_question_length = MAX_EMBED_DESCRIPTION_LENGTH - format_overhead - 10

        if len(question) > max_question_length:
            truncated_question = question[:max_question_length] + "..."
        else:
            truncated_question = question

        result_embed = build_response_embed(
            title="",
            description=f"### {display_name} asked:\n{truncated_question}\n### 🎱 8-ball answered:\n{eight_ball_response}",
            color=discord.Colour.from_rgb(0, 0, 0),
        )
        result_embed.set_thumbnail(url=response["thumbnail_url"])

        await message.edit(embed=result_embed)

    except (FileNotFoundError, ValueError, KeyError, RuntimeError) as e:
        logger.error(f"Error in eight_ball command: {e}")
        await send_error_response(
            interaction,
            f"Failed to consult the Magic 8-Ball. Contact staff for a refund, sorry!",
        )
