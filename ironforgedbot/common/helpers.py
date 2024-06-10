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
    return "".join(new_nick)


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
