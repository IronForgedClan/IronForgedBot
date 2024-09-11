import logging
from io import BytesIO
from typing import Tuple, TypedDict

import discord
import requests
from discord import Guild, Member

from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


class EmojiCache(TypedDict):
    id: int
    animated: bool


emojiCache: dict[str, EmojiCache] = {}
QUOTES = "```"
MAX_DISCORD_MESSAGE_SIZE = 2_000 - len(QUOTES) - 1
NEW_LINE = "\n"


def normalize_discord_string(nick: str) -> str:
    """Strips Discord nickname down to plaintext."""
    if nick is None:
        return ""

    if nick.isascii():
        return nick

    new_nick = []
    for letter in nick:
        if letter.isascii():
            new_nick.append(letter)
    return "".join(new_nick).strip()


def validate_playername(
    guild: discord.Guild, playername: str, must_be_member: bool = True
) -> Tuple[Member | None, str]:
    playername = normalize_discord_string(playername)

    if len(playername) > 12 or len(playername) < 1:
        raise ValueError("RSN can only be 1-12 characters long")

    if must_be_member:
        return find_member_by_nickname(guild, playername), playername

    # If membership is optional, still attempt to grab member object.
    # This allows correct username casing, server emojis etc
    try:
        return find_member_by_nickname(guild, playername), playername
    except ValueError:
        return None, playername


def validate_member_has_role(member: Member, required_role: str) -> bool:
    for role in member.roles:
        if role.name.lower() == required_role.lower():
            return True

    return False


def find_member_by_nickname(guild: Guild, target_name: str) -> Member:
    if not guild.members or len(guild.members) < 1:
        raise ReferenceError("Error accessing server members")

    for member in guild.members:
        normalized_display_name = normalize_discord_string(member.display_name.lower())
        if normalized_display_name == normalize_discord_string(target_name.lower()):
            if not member.nick or len(member.nick) < 1:
                logger.info(f"{member.display_name} has no nickname set")
                raise ValueError(
                    f"Member '**{member.display_name}**' does not have a nickname set"
                )
            return member

    raise ValueError(f"Player '**{target_name}**' is not a member of this server")


def calculate_percentage(part, whole) -> float:
    return 100 * float(part) / float(whole)


def render_percentage(part, whole) -> str:
    value = calculate_percentage(part, whole)

    if value < 1:
        return "<1%"
    if value > 99:
        return ">99%"

    return f"{round(value)}%"


# TODO: Use discord.py implementation when v2.5 released
def populate_emoji_cache(application_id: int):
    headers = {
        "Authorization": f"Bot {CONFIG.BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.get(
        f"https://discord.com/api/applications/{application_id}/emojis",
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()

    for emoji in data["items"]:
        emojiCache[emoji["name"]] = {"id": emoji["id"], "animated": emoji["animated"]}

    logger.info("Emoji cache loaded successfully")


# TODO: when discord.py 2.5 releases remove interaction parameter
def find_emoji(interaction: discord.Interaction, target: str):
    emoji = None

    if target in emojiCache:
        emoji = emojiCache[target]

    assert interaction.guild

    if emoji is None:
        # fallback if not found in cache, search the guild
        for guild_emoji in interaction.guild.emojis:
            if guild_emoji.available and guild_emoji.name == target:
                logger.warning(
                    f"Requested emoji '{guild_emoji.name}' found in guild not cache"
                )
                emojiCache[guild_emoji.name] = {
                    "id": guild_emoji.id,
                    "animated": guild_emoji.animated,
                }
                emoji = emojiCache[guild_emoji.name]

    if emoji is None:
        logger.warning(f"Requested emoji '{target}' not found")
        return ""

    return f"<{'a' if emoji['animated'] else ''}:{target}:{emoji['id']}>"


def get_all_discord_members(guild: discord.Guild) -> list[str]:
    known_members = []
    for member in guild.members:
        if member.bot or member.nick is None or "" == member.nick:
            continue

        nick = normalize_discord_string(member.nick)
        if "" == nick:
            continue

        for role in member.roles:
            normalized_role = normalize_discord_string(role.name)
            if "" == normalized_role:
                continue

            if "member" == normalized_role.lower():
                known_members.append(nick)

    return known_members


def fit_log_lines_into_discord_messages(lines: list[str]) -> list[str]:
    messages = []
    current_message = QUOTES + NEW_LINE

    for line in lines:
        if len(line) + len(current_message) > MAX_DISCORD_MESSAGE_SIZE:
            current_message += QUOTES
            messages.append(current_message)
            current_message = QUOTES + NEW_LINE
        current_message += line + NEW_LINE

    if len(current_message) > len(QUOTES) + len(NEW_LINE):
        current_message += QUOTES
        messages.append(current_message)

    return messages


async def reply_with_file(
    msg: str, body: str, file_name: str, interaction: discord.Interaction
):
    discord_file = discord.File(BytesIO(str.encode(body)), filename=file_name)
    await interaction.followup.send(msg, file=discord_file)
