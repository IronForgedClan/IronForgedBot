import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
import time

import discord
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
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold, text_h2
from ironforgedbot.http import HTTP, HttpException
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.services.score_service import (
    HiscoresError,
    HiscoresNotFound,
    ScoreService,
)

logger = logging.getLogger(__name__)

PROBATION_DAYS = 14


async def _sleep():
    sleep = round(random.uniform(0.2, 1.5), 2)
    logger.debug(f"...sleeping {sleep}s")
    await asyncio.sleep(sleep)


async def job_refresh_ranks(guild: discord.Guild, report_channel: discord.TextChannel):
    now = datetime.now(timezone.utc)
    start_time = time.perf_counter()

    random_rank = random.choice(RANK.list())
    icon = find_emoji(random_rank)

    primary_message_str = (
        f"{text_h2(f'{icon} Rank & Probation Check')}\n"
        f"Initiated: {datetime_to_discord_relative(now, 't')}\n"
    )

    progress_message = await report_channel.send(
        primary_message_str + f"Progress: **0/{guild.member_count}]**"
    )

    async for session in db.get_session():
        service = MemberService(session)

        for index, member in enumerate(guild.members):
            if index > 0:
                await _sleep()

            logger.debug(f"Processing member: {member.display_name}")

            await progress_message.edit(
                content=primary_message_str
                + f"Progress: **{index + 1}/{guild.member_count}**"
            )

            if (
                member.bot
                or check_member_has_role(member, ROLE.APPLICANT)
                or check_member_has_role(member, ROLE.GUEST)
            ):
                logger.debug("...ignoring bot/applicant/guest")
                continue

            if member.nick is None or len(member.nick) < 1:
                logger.debug("...has no nickname")
                message = f"{member.mention} has no nickname set, ignoring..."
                await report_channel.send(message)
                continue

            current_rank = get_rank_from_member(member)

            if current_rank in GOD_ALIGNMENT:
                logger.debug("...has God alignment")
                continue

            if current_rank == RANK.GOD:
                logger.debug("...has God role but no alignment")
                message = (
                    f"{member.mention} has {find_emoji(current_rank)} "
                    "God rank but no alignment."
                )
                await report_channel.send(message)
                continue

            score_service = ScoreService(HTTP)
            current_points = 0
            try:
                current_points = await score_service.get_player_points_total(
                    member.display_name
                )
            except HttpException as e:
                await report_channel.send(
                    f"HttpException getting points for {member.mention}.\n> {e}"
                )
                continue
            except HiscoresError:
                await report_channel.send(
                    f"Unhandled error getting points for {member.mention}."
                )
                continue
            except HiscoresNotFound:
                current_points = 0
                if (
                    not check_member_has_role(member, ROLE.PROSPECT)
                    and current_rank != RANK.IRON
                ):
                    logger.debug("...suspected name change or ban")
                    await report_channel.send(
                        f"{member.mention} has no presence on the hiscores. This member "
                        "has either changed their rsn, or been banned."
                    )
                    continue

            correct_rank = get_rank_from_points(current_points)
            storage_member = await service.get_member_by_nickname(member.display_name)

            if not storage_member:
                logger.debug("...not found in db")
                await report_channel.send(f"{member.mention} not found in database.")
                continue

            if correct_rank != storage_member.rank:
                logger.debug("...updating db")
                await service.change_rank(storage_member.id, RANK(correct_rank))

            if check_member_has_role(member, ROLE.PROSPECT):
                if not isinstance(storage_member.joined_date, datetime):
                    logger.debug("...has invalid join date")
                    await report_channel.send(
                        f"{member.mention} is a {text_bold(ROLE.PROSPECT)} with an invalid join date."
                    )
                    continue

                if datetime.now(timezone.utc) >= storage_member.joined_date + timedelta(
                    days=PROBATION_DAYS
                ):
                    logger.debug("...completed probation")
                    await report_channel.send(
                        f"{member.mention} has completed their "
                        f"{text_bold(f'{PROBATION_DAYS} day')} probation period and is now "
                        f"eligible for {find_emoji(correct_rank)} {text_bold(correct_rank)} rank."
                    )
                    continue

                logger.debug("...still on probation")
                continue

            if current_rank is None:
                logger.debug("...has no rank set")
                await report_channel.send(
                    f"{member.mention} detected without any rank. Should have "
                    f"{find_emoji(correct_rank)} {text_bold(correct_rank)}."
                )
                continue

            if current_rank != str(correct_rank):
                logger.debug("...needs upgrading")
                message = (
                    f"{member.mention} needs upgrading {find_emoji(current_rank)} "
                    f"→ {find_emoji(correct_rank)} ({text_bold(f'{current_points:,}')} points)"
                )
                await report_channel.send(message)
                continue

            logger.debug("...no change")

        await service.close()

        end_time = time.perf_counter()
        await report_channel.send(
            f"**Rank & probation check:** completed in **{format_duration(start_time, end_time)}**."
        )
