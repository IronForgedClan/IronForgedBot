import logging
import re
from datetime import datetime
from io import BytesIO
import sys
from typing import List, Tuple, TypedDict

import discord
import pytz
from dateutil.relativedelta import relativedelta
from discord import Guild, Member
from discord.utils import get

from ironforgedbot.common.constants import MAX_DISCORD_MESSAGE_SIZE, NEW_LINE, QUOTES
from ironforgedbot.common.roles import ROLE

logger = logging.getLogger(__name__)


class EmojiCache(TypedDict):
    id: int
    animated: bool


emojiCache: dict[str, EmojiCache] = {}


def normalize_discord_string(input: str) -> str:
    """Strips string down to plaintext."""
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # Emoticons
        "\U0001f300-\U0001f5ff"  # Symbols & Pictographs
        "\U0001f680-\U0001f6ff"  # Transport & Map Symbols
        "\U0001f700-\U0001f77f"  # Alchemical Symbols
        "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
        "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols & Pictographs
        "\U0001fa00-\U0001fa6f"  # Chess Symbols, Symbols & Pictographs Extended-A
        "\U0001fa70-\U0001faff"  # Symbols & Pictographs Extended-B
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"  # Enclosed characters
        "\U00002000-\U0000201f"  # Miscellaneous Symbols
        "\U0000fe00-\U0000fe0f"  # Variation Selectors (used with emojis)
        "\U0001f004"  # Mahjong Tiles
        "\U0001f0cf"  # Playing Cards
        "\U0001f1e0-\U0001f1ff"  # Regional indicator symbols (flags)
        "\U0001f200-\U0001f251"  # Enclosed Alphanumeric Supplement
        "\U0001f004-\U0001f0cf"  # Mahjong Tiles, Playing Cards
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


async def populate_emoji_cache(emojis: list[discord.Emoji]):
    for e in emojis:
        emojiCache[e.name] = {
            "id": e.id,
            "animated": e.animated,
        }

    logger.info(f"Emoji cache loaded {len(emojiCache)} successfully")


def find_emoji(target: str):
    emoji = None
    if target in emojiCache:
        emoji = emojiCache[target]

    if emoji is None:
        logger.warning(f"Requested emoji '{target}' not found in cache")
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


def datetime_to_discord_relative(dt: datetime, format="d") -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)

    unix_timestamp = int(dt.timestamp())

    return f"<t:{unix_timestamp}:{format}>"


def get_discord_role(guild: discord.Guild, role: ROLE) -> discord.Role | None:
    return get(guild.roles, name=role)


def format_duration(start: float, end: float) -> str:
    """Formats a time duration into the most relevant unit (ms, s, min, hr)."""
    duration = end - start

    if duration < 1e-3:  # Less than 1 ms
        return f"{duration * 1e6:.2f} µs"
    elif duration < 1:  # Less than 1 second
        return f"{duration * 1e3:.2f} ms"
    elif duration < 60:  # Less than 1 minute
        return f"{duration:.2f} s"
    elif duration < 3600:  # Less than 1 hour
        return f"{duration / 60:.2f} min"
    else:  # More than 1 hour
        return f"{duration / 3600:.2f} hr"


def deep_getsizeof(obj, seen=None):
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum(
            (deep_getsizeof(k, seen) + deep_getsizeof(v, seen)) for k, v in obj.items()
        )
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(deep_getsizeof(i, seen) for i in obj)

    return size
