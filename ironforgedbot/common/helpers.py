import logging
from typing import Tuple
from discord import Interaction, Guild, Member
import tempfile
from io import BytesIO

import discord
from collections.abc import Sequence

emojiCache = dict[str, discord.Emoji]()

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


def validate_user_request(
    interaction: Interaction, playername: str
) -> Tuple[Member, str]:
    if not interaction.guild:
        logging.error(f"Error accessing guild ({interaction.id})")
        raise ReferenceError("Error accessing server")

    if interaction.is_expired():
        logging.info(f"Interaction has expired ({interaction.id})")
        raise ReferenceError("Interaction has expired")

    playername = validate_playername(playername)
    member = find_member_by_nickname(interaction.guild, playername)

    return member, playername


def validate_playername(playername: str) -> str:
    playername = normalize_discord_string(playername)

    if len(playername) > 12 or len(playername) < 1:
        logging.info(f"RSN length incorrect: '{playername}'")
        raise ValueError("RSN can only be 1-12 characters long")

    return playername


def validate_protected_request(
    interaction: Interaction, playername: str, required_role: str
) -> Tuple[Member, str]:
    caller, _ = validate_user_request(interaction, interaction.user.display_name)
    member, playername = validate_user_request(interaction, playername)

    has_role = validate_member_has_role(caller, required_role)

    if not has_role:
        raise ValueError(
            f"Member '{caller.display_name}' does not have permission for this action"
        )

    return member, playername


def validate_member_has_role(member: Member, required_role: str) -> bool:
    roles = member.roles

    for role in roles:
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
                logging.info(f"{member.display_name} has no nickname set")
                raise ValueError(
                    f"Member '**{member.display_name}**' does not have a nickname set"
                )
            return member

    raise ValueError(f"Player '**{target_name}**' is not a member of this server")


def calculate_percentage(part, whole) -> int:
    return round(100 * float(part) / float(whole))


def find_emoji(list_: Sequence[discord.Emoji], target: str):
    if target in emojiCache:
        return emojiCache[target]

    for emoji in list_:
        if emoji.available and emoji.name == target:
            emojiCache[emoji.name] = emoji
            return emoji

    return ""


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
