import logging
from datetime import datetime
from io import BytesIO
from typing import List, Tuple, TypedDict

import discord
import pytz
from discord import Guild, Member
from discord.utils import get

from ironforgedbot.common.constants import MAX_DISCORD_MESSAGE_SIZE, NEW_LINE, QUOTES
from ironforgedbot.common.roles_discord import ROLE
from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


class EmojiCache(TypedDict):
    id: int
    animated: bool


emojiCache: dict[str, EmojiCache] = {}


def validate_playername(
    guild: discord.Guild, playername: str, must_be_member: bool = True
) -> Tuple[Member | None, str]:
    from ironforgedcore.common.normalize import normalize_discord_string

    playername = normalize_discord_string(playername)

    if len(playername) > 12 or len(playername) < 1:
        raise ValueError("RSN can only be 1-12 characters long")

    if must_be_member:
        return find_member_by_nickname(guild, playername), playername

    try:
        return find_member_by_nickname(guild, playername), playername
    except ValueError:
        return None, playername


def find_member_by_nickname(guild: Guild, target_name: str) -> Member:
    from ironforgedcore.common.normalize import normalize_discord_string

    if not guild.members or len(guild.members) < 1:
        raise ReferenceError("Error accessing server members")

    for member in guild.members:
        normalized_display_name = normalize_discord_string(member.display_name.lower())
        if normalized_display_name == normalize_discord_string(target_name.lower()):
            if not member.nick or len(member.nick) < 1:
                logger.debug(f"{member.display_name} has no nickname set")
                raise ValueError(
                    f"Member '**{member.display_name}**' does not have a nickname set"
                )
            return member

    raise ValueError(f"Player '**{target_name}**' is not a member of this server")


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
    from ironforgedcore.common.normalize import normalize_discord_string

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


def build_discord_link(channel_id: int) -> str:
    return f"https://discord.com/channels/{CONFIG.GUILD_ID}/{channel_id}"
