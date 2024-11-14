import logging
from datetime import datetime
from io import BytesIO
import re
from typing import List, Optional, Tuple, TypedDict

import discord
from dateutil.relativedelta import relativedelta
from discord import Guild, Member

from ironforgedbot.common.constants import MAX_DISCORD_MESSAGE_SIZE, NEW_LINE, QUOTES
from ironforgedbot.common.roles import ROLE
from ironforgedbot.http import HTTP

logger = logging.getLogger(__name__)


class EmojiCache(TypedDict):
    id: int
    animated: bool


emojiCache: dict[str, EmojiCache] = {}


def normalize_discord_string(input: str) -> str:
    """Strips string down to plaintext."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        "\U0001F700-\U0001F77F"  # Alchemical Symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols & Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols, Symbols & Pictographs Extended-A
        "\U0001FA70-\U0001FAFF"  # Symbols & Pictographs Extended-B
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"  # Enclosed characters
        "\U00002000-\U0000201F"  # Miscellaneous Symbols
        "\U0000FE00-\U0000FE0F"  # Variation Selectors (used with emojis)
        "\U0001F004"  # Mahjong Tiles
        "\U0001F0CF"  # Playing Cards
        "\U0001F1E0-\U0001F1FF"  # Regional indicator symbols (flags)
        "\U0001F200-\U0001F251"  # Enclosed Alphanumeric Supplement
        "\U0001F004-\U0001F0CF"  # Mahjong Tiles, Playing Cards
        "]+",
        flags=re.UNICODE,
    )
    string_without_emojis = emoji_pattern.sub(r"", input)

    # Only keep characters that are within the ASCII range
    ascii_string = "".join([char for char in string_without_emojis if ord(char) < 128])

    # Replace multiple spaces with a single space and strip leading/trailing spaces
    return re.sub(r"\s+", " ", ascii_string).strip()


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


def check_member_has_role(
    member: Member,
    required_role: ROLE,
    or_higher: Optional[bool] = False,
    or_lower: Optional[bool] = False,
) -> bool:
    member_roles = set(role.name for role in member.roles)
    acceptable_roles = set([required_role.value])

    if or_higher:
        acceptable_roles = set(ROLE(required_role).or_higher())

    if or_lower:
        acceptable_roles = set(ROLE(required_role).or_lower())

    member_roles = {role.lower().strip() for role in member_roles}
    acceptable_roles = {role.lower().strip() for role in acceptable_roles}

    if acceptable_roles & member_roles:
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
    whole = 1 if whole == 0 else whole
    return 100 * float(part) / float(whole)


def render_percentage(part, whole) -> str:
    value = calculate_percentage(part, whole)

    if value < 1:
        return "<1%"
    if value > 99:
        return ">99%"

    return f"{round(value)}%"


# TODO: Use discord.py implementation when v2.5 released
async def populate_emoji_cache(application_id: int, token: str):
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }

    data = await HTTP.get(
        url=f"https://discord.com/api/applications/{application_id}/emojis",
        headers=headers,
    )

    if data:
        for emoji in data["items"]:
            emojiCache[emoji["name"]] = {
                "id": emoji["id"],
                "animated": emoji["animated"],
            }

        logger.info("Emoji cache loaded successfully")
    else:
        logger.critical("Error populating emoji cache")


# TODO: when discord.py 2.5 releases remove interaction param and fallback
def find_emoji(interaction: discord.Interaction | None, target: str):
    emoji = None

    if target in emojiCache:
        emoji = emojiCache[target]

    # fallback if not found in cache, search the guild
    if emoji is None and interaction is not None:
        assert interaction.guild

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


def get_all_discord_members(guild: discord.Guild) -> List[str]:
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


def fit_log_lines_into_discord_messages(lines: List[str]) -> List[str]:
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


def render_relative_time(target: datetime) -> str:
    delta = relativedelta(datetime.now().astimezone(), target)

    if delta.years > 0:
        return f"{delta.years} year{'s' if delta.years > 1 else ''} ago"
    elif delta.months > 0:
        return f"{delta.months} month{'s' if delta.months > 1 else ''} ago"
    elif delta.days > 6:
        weeks = delta.days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    elif delta.hours > 0:
        return f"{delta.hours} hour{'s' if delta.hours > 1 else ''} ago"
    elif delta.minutes > 0:
        return f"{delta.minutes} minute{'s' if delta.minutes > 1 else ''} ago"
    else:
        return f"{delta.seconds} second{'s' if delta.seconds != 1 else ''} ago"


def get_text_channel(
    guild: discord.Guild | None, channel_id: int
) -> discord.TextChannel | None:
    if not guild:
        return None

    for channel in guild.channels:
        if channel.id == channel_id and channel.type == discord.ChannelType.text:
            return channel

    return None
