from discord import Emoji
from collections.abc import Sequence

emojiCache = dict[str, Emoji]()


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


def find_emoji(list: Sequence[Emoji], target: str) -> Emoji | str:
    if target in emojiCache:
        return emojiCache[target]

    for emoji in list:
        if emoji.available and emoji.name == target:
            emojiCache[emoji.name] = emoji
            return emoji

    return ":question:"
