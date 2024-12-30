import asyncio
import logging
import random

import discord

from ironforgedbot.commands.hiscore.calculator import get_player_points_total
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.ranks import (
    GOD_ALIGNMENT,
    RANK,
    get_rank_from_member,
    get_rank_from_points,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold

logger = logging.getLogger(__name__)


async def job_refresh_ranks(guild: discord.Guild, report_channel: discord.TextChannel):
    await report_channel.send("Beginning rank check...")

    for member in guild.members:
        if (
            member.bot
            or check_member_has_role(member, ROLE.PROSPECT)
            or check_member_has_role(member, ROLE.APPLICANT)
            or check_member_has_role(member, ROLE.GUEST)
        ):
            continue

        if member.nick is None or len(member.nick) < 1:
            message = (
                f"{member.mention} is not a Prospect, Applicant, Guest or Bot "
                "and has no nickname set, ignoring..."
            )
            await report_channel.send(message)
            continue

        current_rank = get_rank_from_member(member)

        if current_rank in GOD_ALIGNMENT:
            continue

        if current_rank == RANK.GOD:
            message = f"{member.mention} has God role but no alignment."
            await report_channel.send(message)
            continue

        if current_rank is None:
            message = f"{member.mention} detected without any ranked role, ignoring..."
            await report_channel.send(message)
            continue

        try:
            current_points = await get_player_points_total(member.display_name)
        except Exception as e:
            logger.error(e)
            await report_channel.send(
                f"Error calculating points for {member.mention}. Is their nickname correct?"
            )
            continue

        correct_rank = get_rank_from_points(current_points)
        if current_rank != str(correct_rank):
            message = (
                f"{member.mention} needs upgrading {find_emoji(None, current_rank)} "
                f"→ {find_emoji(None, correct_rank)} ({text_bold(f"{current_points:,}")} points)"
            )
            await report_channel.send(message)

        await asyncio.sleep(random.randrange(1, 3))

    await report_channel.send("Finished rank check.")
