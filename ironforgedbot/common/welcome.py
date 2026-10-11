import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import discord

WELCOME_DATA_FILE = "data/welcome.json"
WELCOME_DATA_DIRECTORY = Path(WELCOME_DATA_FILE).parent
WELCOME_CHANNEL_PLACEHOLDERS = {
    "{{RULES_CHANNEL}}": "RULES_CHANNEL_ID",
    "{{BOT_COMMANDS_CHANNEL}}": "BOT_COMMANDS_CHANNEL_ID",
    "{{INGOT_SHOP_CHANNEL}}": "INGOT_SHOP_CHANNEL_ID",
    "{{CREATE_TICKET_CHANNEL}}": "CREATE_TICKET_CHANNEL_ID",
    "{{RANKINGS_CHANNEL}}": "RANKINGS_CHANNEL_ID",
    "{{RAFFLE_CHANNEL}}": "RAFFLE_CHANNEL_ID",
}
WELCOME_EMOJI_PATTERN = re.compile(r"\{\{EMOJI:([A-Za-z0-9_]+)\}\}")


@dataclass(frozen=True)
class WelcomeMessage:
    content: str
    image: str | None = None


def load_welcome_messages(
    file_path: str = WELCOME_DATA_FILE,
) -> list[WelcomeMessage]:
    with open(file_path, encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise ValueError(f"Welcome data must contain a messages array: {file_path}")

    messages: list[WelcomeMessage] = []
    for index, item in enumerate(data["messages"]):
        if not isinstance(item, dict):
            raise ValueError(f"Welcome message {index} must be an object")

        content = item.get("content", "")
        image = item.get("image")
        if not isinstance(content, str):
            raise ValueError(f"Welcome message {index} content must be a string")
        if image is not None and not isinstance(image, str):
            raise ValueError(f"Welcome message {index} image must be a string")
        if not content.strip() and not image:
            raise ValueError(
                f"Welcome message {index} must contain content or an image"
            )

        if image and "://" in image:
            parsed_image = urlparse(image)
            if parsed_image.scheme not in {"http", "https"} or not parsed_image.netloc:
                raise ValueError(f"Welcome message {index} image URL is invalid")

        messages.append(WelcomeMessage(content=content, image=image))

    if not messages:
        raise ValueError("Welcome data must contain at least one message")

    return messages


def format_welcome_content(content: str, channel_ids: dict[str, int]) -> str:
    for placeholder, config_key in WELCOME_CHANNEL_PLACEHOLDERS.items():
        if placeholder not in content:
            continue

        channel_id = channel_ids.get(config_key)
        if not channel_id:
            raise ValueError(f"Welcome channel is not configured: {config_key}")
        content = content.replace(placeholder, f"<#{channel_id}>")

    return WELCOME_EMOJI_PATTERN.sub(
        lambda match: _resolve_welcome_emoji(match.group(1)), content
    )


def _resolve_welcome_emoji(name: str) -> str:
    from ironforgedbot.common.helpers import find_emoji

    return find_emoji(name) or f":{name}:"


async def send_welcome_messages(
    user: discord.User | discord.Member,
    messages: list[WelcomeMessage] | None = None,
    data_directory: str | Path = WELCOME_DATA_DIRECTORY,
) -> None:
    if messages is None:
        messages = load_welcome_messages()
    if not messages:
        raise ValueError("Welcome data must contain at least one message")

    channel_ids: dict[str, int] = {}
    if any(
        placeholder in message.content
        for message in messages
        for placeholder in WELCOME_CHANNEL_PLACEHOLDERS
    ):
        from ironforgedbot.config import CONFIG

        channel_ids = {
            config_key: getattr(CONFIG, config_key)
            for config_key in WELCOME_CHANNEL_PLACEHOLDERS.values()
        }

    data_root = Path(data_directory).resolve()
    for message in messages:
        content = format_welcome_content(message.content, channel_ids)
        if not message.image:
            await user.send(content=content)
            continue

        embed = discord.Embed(description=content or None)
        if _is_url(message.image):
            embed.set_image(url=message.image)
            await user.send(embed=embed)
            continue

        image_path = (data_root / message.image).resolve()
        try:
            image_path.relative_to(data_root)
        except ValueError as error:
            raise ValueError(
                "Welcome image path resolves outside the data directory"
            ) from error
        if not image_path.is_file():
            raise FileNotFoundError(f"Welcome image file not found: {image_path}")

        embed.set_image(url=f"attachment://{image_path.name}")
        image_file = discord.File(str(image_path), filename=image_path.name)
        try:
            await user.send(
                embed=embed,
                file=image_file,
            )
        finally:
            image_file.close()


def _is_url(value: str) -> bool:
    parsed_value = urlparse(value)
    return parsed_value.scheme in {"http", "https"} and bool(parsed_value.netloc)
