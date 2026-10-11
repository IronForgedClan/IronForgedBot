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
MAX_EMBEDS_PER_MESSAGE = 10
MAX_EMBED_DESCRIPTION_LENGTH = 4096
MAX_EMBED_CHARACTERS_PER_MESSAGE = 6000


@dataclass(frozen=True)
class WelcomeMessage:
    content: str
    image: str | None = None


@dataclass(frozen=True)
class _PreparedWelcomeEmbed:
    embed: discord.Embed
    image_path: Path | None = None
    filename: str | None = None


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

    prepared_embeds = _prepare_welcome_embeds(
        messages, channel_ids, Path(data_directory).resolve()
    )
    batches: list[list[_PreparedWelcomeEmbed]] = []
    current_batch: list[_PreparedWelcomeEmbed] = []
    current_character_count = 0
    for prepared in prepared_embeds:
        description_length = len(prepared.embed.description or "")
        if current_batch and (
            len(current_batch) >= MAX_EMBEDS_PER_MESSAGE
            or current_character_count + description_length
            > MAX_EMBED_CHARACTERS_PER_MESSAGE
        ):
            batches.append(current_batch)
            current_batch = []
            current_character_count = 0

        current_batch.append(prepared)
        current_character_count += description_length

    if current_batch:
        batches.append(current_batch)

    for batch in batches:
        image_files: list[discord.File] = []
        try:
            for prepared in batch:
                if prepared.image_path:
                    image_files.append(
                        discord.File(
                            str(prepared.image_path), filename=prepared.filename
                        )
                    )

            embeds = [prepared.embed for prepared in batch]
            if image_files:
                await user.send(embeds=embeds, files=image_files)
            else:
                await user.send(embeds=embeds)
        finally:
            for image_file in image_files:
                image_file.close()


def _prepare_welcome_embeds(
    messages: list[WelcomeMessage], channel_ids: dict[str, int], data_root: Path
) -> list[_PreparedWelcomeEmbed]:
    prepared_embeds: list[_PreparedWelcomeEmbed] = []
    for message_index, message in enumerate(messages):
        content = format_welcome_content(message.content, channel_ids)
        image_path = None
        filename = None
        if message.image and not _is_url(message.image):
            image_path = (data_root / message.image).resolve()
            try:
                image_path.relative_to(data_root)
            except ValueError as error:
                raise ValueError(
                    "Welcome image path resolves outside the data directory"
                ) from error
            if not image_path.is_file():
                raise FileNotFoundError(f"Welcome image file not found: {image_path}")
            filename = f"welcome_{message_index}_{image_path.name}"

        content_chunks = _split_welcome_content(content)
        for chunk_index, content_chunk in enumerate(content_chunks):
            embed = discord.Embed(description=content_chunk or None)
            prepared_image_path = None
            prepared_filename = None
            if chunk_index == 0 and message.image:
                if image_path:
                    embed.set_image(url=f"attachment://{filename}")
                    prepared_image_path = image_path
                    prepared_filename = filename
                else:
                    embed.set_image(url=message.image)

            prepared_embeds.append(
                _PreparedWelcomeEmbed(
                    embed=embed,
                    image_path=prepared_image_path,
                    filename=prepared_filename,
                )
            )

    return prepared_embeds


def _split_welcome_content(content: str) -> list[str]:
    if not content:
        return [""]

    chunks: list[str] = []
    while len(content) > MAX_EMBED_DESCRIPTION_LENGTH:
        split_at = content.rfind("\n", 0, MAX_EMBED_DESCRIPTION_LENGTH)
        if split_at <= 0:
            split_at = MAX_EMBED_DESCRIPTION_LENGTH
        chunks.append(content[:split_at])
        content = content[split_at:]
    chunks.append(content)
    return chunks


def _is_url(value: str) -> bool:
    parsed_value = urlparse(value)
    return parsed_value.scheme in {"http", "https"} and bool(parsed_value.netloc)
