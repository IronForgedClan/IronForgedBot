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
from ironforgedbot.common.ranks import get_rank_from_member, get_rank_from_points
from ironforgedbot.common.text_formatters import text_bold

logger = logging.getLogger(__name__)


async def job_refresh_ranks(guild: discord.Guild, report_channel: discord.TextChannel):
    members_to_update = {}
    await report_channel.send("Beginning rank check...")

    for member in guild.members:
        nick = normalize_discord_string(member.nick or "")

        if member.bot or member.nick is None or member.nick == "":
            logger.info(f"Skipping rank check for: {member.display_name}")
            continue

        current_rank = get_rank_from_member(member, ignore_prospect=True)

        if current_rank is None:
            message = f"Member {member.mention} detected without any ranked role."
            logger.warning(message)
            await report_channel.send(message)
            continue

        members_to_update[nick] = current_rank

    for nick, current_rank in members_to_update.items():
        member = find_member_by_nickname(guild, nick)
        try:
            current_points = await get_player_points_total(nick)
        except Exception as e:
            logger.error(f"Error processing {nick}: {e}")
            await report_channel.send(
                f"Error calculating points for {member.mention}. Is their rsn correct?"
            )
            continue

        correct_rank = get_rank_from_points(current_points)
        if current_rank != str(correct_rank):
            message = (
                f"{member.mention} upgraded their rank {find_emoji(None, current_rank)} "
                f"→ {find_emoji(None, correct_rank)} with {text_bold(f"{current_points:,}")} points."
            )
            await report_channel.send(message)

        await asyncio.sleep(random.randrange(1, 5))

    await report_channel.send("Finished rank check.")
