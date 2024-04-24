import random
import time

import asyncio
import discord

from ironforgedbot.commands.hiscore.calculator import points_total
from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANKS, get_rank_from_points


def refresh_ranks(
    guild: discord.Guild, updates_channel_name: str, loop: asyncio.BaseEventLoop
):
    if updates_channel_name is None or "" == updates_channel_name:
        return

    updates_channel = _find_channel(guild, updates_channel_name)
    if updates_channel is None:
        return

    icons = _load_icons(guild)
    members_to_update = {}

    # Just in case we don't want to handle routing from guild.members
    for member in guild.members:
        if member.bot or member.nick is None or "" == member.nick:
            continue

        nick = normalize_discord_string(member.nick)
        if "" == nick:
            continue

        current_role = _find_rank(member)
        if current_role is None:
            continue

        members_to_update[nick] = current_role

    asyncio.run_coroutine_threadsafe(_send_message(
            updates_channel, f'Starting daily ranks check for {len(members_to_update)} members'), loop)

    for member, current_role in members_to_update.items():
        try:
            current_points = points_total(member)
        except RuntimeError:
            continue

        actual_role = get_rank_from_points(current_points)
        if current_role != str(actual_role):
            message = (
                f"{member} has upgraded their rank from {icons[current_role]} to {icons[actual_role]} "
                f"with {current_points} points"
            )
            asyncio.run_coroutine_threadsafe(
                _send_message(updates_channel, message), loop
            )

        time.sleep(random.randint(1, 5))

    asyncio.run_coroutine_threadsafe(_send_message(updates_channel, f'Finished daily ranks check'), loop)


async def _send_message(channel, message):
    await channel.send(content=message)


def _find_rank(member: discord.Member):
    for role in member.roles:
        normalized_role = normalize_discord_string(role.name)
        if "" == normalized_role:
            continue

        if RANKS.has_value(normalized_role):
            return RANKS(role.name)
    return None


def _find_channel(guild: discord.Guild, channel_name: str):
    for channel in guild.channels:
        if channel.name.lower() == channel_name.lower():
            return channel


def _load_icons(guild: discord.Guild):
    icons = {}
    for rank in RANKS.list():
        for emoji in guild.emojis:
            if emoji.name.lower() == str(rank).lower():
                icons[rank] = emoji
                break

    return icons
