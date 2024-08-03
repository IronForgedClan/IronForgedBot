import asyncio
import logging
import random
import time

import discord

from ironforgedbot.commands.hiscore.calculator import points_total
from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANKS, get_rank_from_points
from ironforgedbot.common.roles import extract_roles, is_member, is_prospect, find_rank
from ironforgedbot.tasks import can_start_task, _send_discord_message_plain

logger = logging.getLogger(__name__)


def job_refresh_ranks(
    guild: discord.Guild, updates_channel_name: str, loop: asyncio.BaseEventLoop
):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Miss-configured task refresh_ranks")
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

        member_roles = extract_roles(member)
        current_role = find_rank(member_roles)
        if current_role is None:
            # Check whether user is a member at all
            if is_member(member_roles) and not is_prospect(member_roles):
                message = f"Found a member {nick} w/o the ranked role"
                logger.warning(message)
                asyncio.run_coroutine_threadsafe(
                    _send_discord_message_plain(updates_channel, message), loop
                )
            continue

        members_to_update[nick] = current_role

    asyncio.run_coroutine_threadsafe(
        _send_discord_message_plain(
            updates_channel,
            f"Starting daily ranks check for {len(members_to_update)} members",
        ),
        loop,
    )

    for member, current_role in members_to_update.items():
        logger.info(f"Checking score for {member}, current rank {current_role}")
        try:
            current_points = points_total(member)
        except RuntimeError as e:
            logger.error(f"Caught error while checking {member}: {e}")
            continue

        actual_role = get_rank_from_points(current_points)
        if current_role != str(actual_role):
            message = (
                f"{member} has upgraded their rank from {icons[current_role]} to {icons[actual_role]} "
                f"with {current_points} points"
            )
            logger.info(message)
            asyncio.run_coroutine_threadsafe(
                _send_discord_message_plain(updates_channel, message), loop
            )

        time.sleep(random.randint(1, 5))

    asyncio.run_coroutine_threadsafe(
        _send_discord_message_plain(updates_channel, f"Finished daily ranks check"),
        loop,
    )


def _load_icons(guild: discord.Guild):
    icons = {}
    for rank in RANKS.list():
        for emoji in guild.emojis:
            if emoji.name.lower() == str(rank).lower():
                icons[rank] = emoji
                break

    return icons
