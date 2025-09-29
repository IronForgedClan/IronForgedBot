import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
import time

import discord
from ironforgedbot.common.roles import ROLE, check_member_has_role, is_member_banned
from ironforgedbot.database.database import db
from ironforgedbot.common.helpers import (
    datetime_to_discord_relative,
    find_emoji,
    format_duration,
)
from ironforgedbot.common.ranks import (
    GOD_ALIGNMENT,
    RANK,
    get_rank_from_member,
    get_rank_from_points,
)
from ironforgedbot.common.text_formatters import text_bold, text_h2
from ironforgedbot.http import HTTP
from ironforgedbot.models.score_history import ScoreHistory
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.services.score_history_service import ScoreHistoryService
from ironforgedbot.services.score_service import (
    HiscoresNotFound,
    ScoreService,
)

logger: logging.Logger = logging.getLogger(name=__name__)

PROBATION_DAYS = 28


async def job_refresh_ranks(
    guild: discord.Guild, report_channel: discord.TextChannel
) -> None:
    now: datetime = datetime.now(tz=timezone.utc)
    start_time: float = time.perf_counter()
    random_rank: str = random.choice(seq=RANK.list())
    icon: str = find_emoji(target=random_rank)
    primary_message_str = (
        f"{text_h2(input=f'{icon} Rank & Probation Check')}\n"
        f"Initiated: {datetime_to_discord_relative(dt=now, format='t')}\n"
    )

    progress_message = await report_channel.send(primary_message_str)

    async with db.get_session() as session:
        member_service = MemberService(session)
        history = ScoreHistoryService(session)
        members = await member_service.get_all_active_members()

        for index, member in enumerate(members):
            if index > 0:
                await asyncio.sleep(round(random.uniform(0.2, 1.5), 2))

            logger.debug(f"Processing member: {member.nickname}")

            _ = await progress_message.edit(
                content=primary_message_str
                + f"Progress: **{index + 1}/{len(members)}**"
            )

            discord_member = guild.get_member(member.discord_id)

            if not discord_member:
                logger.debug("...discord member not found")
                _ = await report_channel.send(
                    (
                        f"Active member {member.nickname} ({member.id}) could not be "
                        "found in this guild."
                    )
                )
                continue

            if is_member_banned(discord_member):
                logger.debug("...banned")
                continue

            current_rank = get_rank_from_member(discord_member)

            score_service = ScoreService(HTTP)
            current_points = 0
            try:
                current_points = await score_service.get_player_points_total(
                    member.nickname, bypass_cache=True
                )
            except HiscoresNotFound:
                if (
                    not check_member_has_role(discord_member, ROLE.PROSPECT)
                    and current_rank != RANK.IRON
                ):
                    logger.debug("...suspected name change or ban")
                    _ = await report_channel.send(
                        (
                            f"{discord_member.mention} has no presence on the hiscores. "
                            "This member has either changed their rsn, or been banned."
                        )
                    )
                    continue
                else:
                    current_points = 0
            except Exception:
                _ = await report_channel.send(
                    f"Unhandled error getting points for {discord_member.mention}."
                )
                continue

            await history.track_score(member.discord_id, current_points)

            if current_rank in GOD_ALIGNMENT:
                logger.debug("...has God alignment")
                continue

            if current_rank == RANK.GOD:
                logger.debug("...has God role but no alignment")
                message = (
                    f"{discord_member.mention} has {find_emoji(current_rank)} "
                    "God rank but no alignment."
                )
                _ = await report_channel.send(message)
                continue

            correct_rank = get_rank_from_points(current_points)

            if check_member_has_role(discord_member, ROLE.PROSPECT):
                if not isinstance(member.joined_date, datetime):
                    logger.debug("...has invalid join date")
                    _ = await report_channel.send(
                        (
                            f"{discord_member.mention} is a {text_bold(ROLE.PROSPECT)} "
                            "with an invalid join date."
                        )
                    )
                    continue

                if datetime.now(timezone.utc) >= member.joined_date + timedelta(
                    days=PROBATION_DAYS
                ):
                    logger.debug("...completed probation")
                    _ = await report_channel.send(
                        (
                            f"{discord_member.mention} has completed their "
                            f"{text_bold(f'{PROBATION_DAYS} day')} probation period and "
                            f"is now eligible for {find_emoji(correct_rank)} "
                            f"{text_bold(correct_rank)} rank."
                        )
                    )
                    continue

                logger.debug("...still on probation")
                continue

            if current_rank is None:
                logger.debug("...has no rank set")
                _ = await report_channel.send(
                    (
                        f"{discord_member.mention} detected without any rank. Should have "
                        f"{find_emoji(correct_rank)} {text_bold(correct_rank)}."
                    )
                )
                continue

            if current_rank != str(correct_rank):
                logger.debug("...needs upgrading")
                message = (
                    f"{discord_member.mention} needs upgrading "
                    f"{find_emoji(current_rank)} → {find_emoji(correct_rank)} "
                    f"({text_bold(f'{current_points:,}')} points)"
                )
                _ = await report_channel.send(message)
                continue

            logger.debug("...no change")

        await member_service.close()

        end_time = time.perf_counter()
        _ = await report_channel.send(
            (
                f"**{icon} Rank & probation check:** Completed in "
                f"**{format_duration(start_time, end_time)}**."
            )
        )
