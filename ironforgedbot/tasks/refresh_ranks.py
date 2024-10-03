import asyncio
import logging
import random

import discord

from ironforgedbot.commands.hiscore.calculator import get_player_points_total
from ironforgedbot.common.helpers import (
    find_emoji,
    find_member_by_nickname,
    normalize_discord_string,
)
from ironforgedbot.common.ranks import get_rank_from_points
from ironforgedbot.common.roles import extract_roles, find_rank, is_member, is_prospect

logger = logging.getLogger(__name__)


async def job_refresh_ranks(guild: discord.Guild, report_channel: discord.TextChannel):
    members_to_update = {}

    await report_channel.send("Beginning rank check...")

    for member in guild.members:
        nick = normalize_discord_string(member.nick or "")

        if member.bot or member.nick is None or member.nick == "":
            logger.info(f"Skipping rank check for: {member.display_name}")
            continue

        member_roles = extract_roles(member)
        current_rank = find_rank(member_roles)

        if current_rank is None:
            if is_member(member_roles) and not is_prospect(member_roles):
                message = f"Member '{nick}' detected without any ranked role."
                logger.warning(message)
                await report_channel.send(message)
            continue

        members_to_update[nick] = current_rank

    for member, current_rank in members_to_update.items():
        try:
            current_points = await get_player_points_total(member)
        except RuntimeError as e:
            logger.error(f"Error while checking {member}: {e}")
            continue

        correct_rank = get_rank_from_points(current_points)
        m = find_member_by_nickname(guild, member)
        if current_rank != str(correct_rank):
            message = (
                f"{m.mention} has upgraded their rank from {find_emoji(None, current_rank)} "
                f"→ {find_emoji(None, correct_rank)} with **{current_points:,}** points."
            )
            await report_channel.send(message)

        await asyncio.sleep(random.randrange(1, 5))

    await report_channel.send("Finished rank check.")
