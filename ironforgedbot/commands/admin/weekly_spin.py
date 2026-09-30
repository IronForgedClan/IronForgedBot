import logging
from typing import Literal

import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedcore.storage import data

logger = logging.getLogger(__name__)

WeeklySpinKind = Literal["sotw", "botw"]


def _lookup_emoji(kind: WeeklySpinKind, winner: str) -> str:
    """Resolve the display emoji for a winning option.

    SOTW: match against data.SKILLS by `name`.
    BOTW: BOTW options can be grouped (e.g. "Callisto or Artio") so the
    leading name is used for the lookup; the original `winner` string is
    preserved for display.
    """
    if kind == "sotw":
        skill = next((s for s in data.SKILLS if s["name"] == winner), None)
        if skill is None:
            return "\U0001f389"
        return find_emoji(skill["emoji_key"]) or "\U0001f389"

    if kind == "botw":
        boss_name = winner.split(" or ")[0]
        boss = next((b for b in data.BOSSES if b["name"] == boss_name), None)
        if boss is None:
            return "\U0001f389"
        return find_emoji(boss["emoji_key"]) or "\U0001f389"

    raise ValueError(f"Unknown weekly spin kind: {kind!r}")


async def post_weekly_spin_result(
    target: discord.abc.Messageable,
    kind: WeeklySpinKind,
    file: discord.File,
    winner: str,
) -> discord.Message:
    """Post a spin GIF plus the spoiler-tagged winner to the weekly channel.

    The header advertises which weekly pick this is (e.g. "## Next BOTW").
    The winner line is wrapped in Discord spoiler tags so viewers choose
    when to reveal it. Two thumb reactions (👍 / 👎) are added so members
    can vote without typing.
    """
    emoji = _lookup_emoji(kind, winner)
    header = f"## Next {kind.upper()}"
    content = f"{header}\n||{emoji} {winner}||"

    msg = await target.send(file=file, content=content)

    await msg.add_reaction("\U0001f44d")
    await msg.add_reaction("\U0001f44e")

    logger.debug(f"Posted {kind.upper()} weekly spin result: {winner}")
    return msg
