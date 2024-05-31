from apscheduler.executors.base import logging
from discord import Emoji
from strenum import StrEnum
from collections.abc import Sequence

emojiCache = dict[str, Emoji]()


def find_emoji(list: Sequence[Emoji], target: str):
    if target in emojiCache:
        return emojiCache[target]

    for emoji in list:
        if emoji.available and emoji.name == target:
            emojiCache[emoji.name] = emoji
            return emoji

    logging.warn(f"Requested emoji '{target}' not found")
    return ""
