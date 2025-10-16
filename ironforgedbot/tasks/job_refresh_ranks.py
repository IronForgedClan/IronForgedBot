import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

import discord
from ironforgedbot.common.roles import ROLE, check_member_has_role, is_member_banned
from ironforgedbot.database.database import db
from ironforgedbot.common.helpers import (
    datetime_to_discord_relative,
    find_emoji,
)
from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.common.ranks import (
    GOD_ALIGNMENT,
    RANK,
    RANK_POINTS,
    get_rank_from_member,
    get_rank_from_points,
)
from ironforgedbot.common.text_formatters import text_bold, text_h2
from ironforgedbot.http import HTTP
from ironforgedbot.services.service_factory import (
    create_member_service,
    create_score_history_service,
)
from ironforgedbot.services.score_service import (
    HiscoresNotFound,
    get_score_service,
)

logger = logging.getLogger(__name__)

PROBATION_DAYS = 28


def build_missing_member_message(nickname: str, member_id: int) -> str:
    return f"- {nickname} (ID: {member_id}) not found in guild"


def build_hiscores_not_found_message(mention: str) -> str:
    return f"- {mention} not found on hiscores - likely RSN change or ban"


def build_fetch_error_message(mention: str) -> str:
    return f"- Failed to fetch points for {mention} - check logs"


def build_god_no_alignment_message(mention: str, rank_emoji: str) -> str:
    return f"- {mention} has {rank_emoji} God rank but missing alignment"


def build_invalid_join_date_message(mention: str, role: str) -> str:
    return f"- {mention} ({text_bold(role)}) has invalid join date"


def build_probation_completed_message(
    mention: str, rank_emoji: str, rank_name: str
) -> str:
    return f"- {mention} is eligible for {rank_emoji} {text_bold(rank_name)}"


def build_missing_rank_message(
    mention: str, rank_emoji: str, rank_name: str, points: int
) -> str:
    return (
        f"- {mention} missing rank, should be "
        f"{rank_emoji} {text_bold(rank_name)} "
        f"({text_bold(f'{points:,}')} points)"
    )


def build_rank_upgrade_message(
    mention: str, old_emoji: str, new_emoji: str, points: int
) -> str:
    return (
        f"- {mention} upgrade "
        f"{old_emoji} → {new_emoji} "
        f"({text_bold(f'{points:,}')} points)"
    )


def build_rank_downgrade_message(
    mention: str, old_emoji: str, new_emoji: str, points: int
) -> str:
    return (
        f"- {mention} downgrade "
        f"{old_emoji} → {new_emoji} "
        f"({text_bold(f'{points:,}')} points) "
        "(Verify before changing)"
    )


async def fetch_member_points(
    member_nickname: str,
    discord_member,
    current_rank: str,
    score_service,
) -> tuple[int, str | None]:
    """
    Fetch member points from hiscores API.

    Args:
        member_nickname: OSRS username
        discord_member: Discord member object
        current_rank: Member's current rank
        score_service: Score service instance

    Returns:
        Tuple of (points, error_message)
        - If successful: (points, None)
        - If error: (0, error_message)
    """
    try:
        points = await score_service.get_player_points_total(
            member_nickname, bypass_cache=True
        )
        return points, None
    except HiscoresNotFound:
        if (
            not check_member_has_role(discord_member, ROLE.PROSPECT)
            and current_rank != RANK.IRON
        ):
            return 0, build_hiscores_not_found_message(discord_member.mention)
        else:
            return 0, None
    except Exception:
        return 0, build_fetch_error_message(discord_member.mention)


def process_member_rank_check(
    member,
    discord_member,
    current_rank: str,
    current_points: int,
) -> tuple[str | None, str | None, str | None]:
    """
    Process a member's rank and probation status.

    Args:
        member: Database member object
        discord_member: Discord member object
        current_rank: Member's current rank
        current_points: Member's OSRS points

    Returns:
        Tuple of (rank_change_msg, probation_msg, issue_msg)
        Only one will be non-None, or all None if no action needed
    """
    if current_rank in GOD_ALIGNMENT:
        logger.debug("...has God alignment")
        return None, None, None

    if current_rank == RANK.GOD:
        logger.debug("...has God role but no alignment")
        return (
            None,
            None,
            build_god_no_alignment_message(
                discord_member.mention, find_emoji(current_rank)
            ),
        )

    correct_rank = get_rank_from_points(current_points)

    if check_member_has_role(discord_member, ROLE.PROSPECT):
        if not isinstance(member.joined_date, datetime):
            logger.debug("...has invalid join date")
            return (
                None,
                None,
                build_invalid_join_date_message(discord_member.mention, ROLE.PROSPECT),
            )

        if datetime.now(timezone.utc) >= member.joined_date + timedelta(
            days=PROBATION_DAYS
        ):
            logger.debug("...completed probation")
            return (
                None,
                build_probation_completed_message(
                    discord_member.mention,
                    find_emoji(correct_rank),
                    correct_rank,
                ),
                None,
            )

        logger.debug("...still on probation")
        return None, None, None

    if current_rank is None or not current_rank:
        logger.debug("...has no rank set")
        return (
            None,
            None,
            build_missing_rank_message(
                discord_member.mention,
                find_emoji(correct_rank),
                correct_rank,
                current_points,
            ),
        )

    if current_rank != str(correct_rank):
        current_rank_points = RANK_POINTS[RANK(current_rank).name]
        correct_rank_points = RANK_POINTS[RANK(correct_rank).name]

        if correct_rank_points > current_rank_points:
            logger.debug("...needs upgrading")
            return (
                build_rank_upgrade_message(
                    discord_member.mention,
                    find_emoji(current_rank),
                    find_emoji(correct_rank),
                    current_points,
                ),
                None,
                None,
            )
        else:
            logger.debug("...flagged for downgrade")
            return (
                build_rank_downgrade_message(
                    discord_member.mention,
                    find_emoji(current_rank),
                    find_emoji(correct_rank),
                    current_points,
                ),
                None,
                None,
            )

    logger.debug("...no change")
    return None, None, None


@log_task_execution(logger)
async def job_refresh_ranks(
    guild: discord.Guild, report_channel: discord.TextChannel
) -> None:
    """
    Refreshes member ranks based on calculated OSRS hiscores points and checks
    probation status.

    Iterates through all active members, fetches their current OSRS hiscores stats,
    calculates points, and compares their actual rank with what they should have
    based on points.

    Reports discrepancies (upgrades/downgrades needed), probation completions,
    and other issues like missing members or name changes.

    Args:
        guild: The Discord guild to process members from.
        report_channel: The Discord text channel where progress and results are reported.

    Returns:
        None
    """
    now: datetime = datetime.now(tz=timezone.utc)
    random_rank: str = random.choice(seq=RANK.list())
    icon: str = find_emoji(target=random_rank)
    primary_message_str = (
        f"{text_h2(input=f'{icon} Checking ranks and probations...')}\n"
        f"Initiated: {datetime_to_discord_relative(dt=now, format='t')}\n"
    )

    progress_message = await report_channel.send(primary_message_str)

    async with db.get_session() as session:
        member_service = create_member_service(session)
        history = create_score_history_service(session)
        members = await member_service.get_all_active_members()

        rank_changes = []
        probation_completed = []
        issues = []

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
                issues.append(build_missing_member_message(member.nickname, member.id))
                continue

            if is_member_banned(discord_member):
                logger.debug("...banned")
                continue

            current_rank = get_rank_from_member(discord_member)

            score_service = get_score_service(HTTP)
            current_points, error_message = await fetch_member_points(
                member.nickname, discord_member, current_rank, score_service
            )

            if error_message:
                logger.debug("...error fetching points")
                issues.append(error_message)
                continue

            await history.track_score(member.discord_id, current_points)

            rank_change_msg, probation_msg, issue_msg = process_member_rank_check(
                member, discord_member, current_rank, current_points
            )

            if rank_change_msg:
                rank_changes.append(rank_change_msg)
            if probation_msg:
                probation_completed.append(probation_msg)
            if issue_msg:
                issues.append(issue_msg)

        await progress_message.delete()

        async def send_category_reports(
            title: str, messages: list[str], emoji: str, description: str = ""
        ):
            if not messages:
                return

            header = f"{text_h2(f'{emoji} {title}')}\n"
            if description:
                header += f"{description}\n\n"
            else:
                header += "\n"

            footer_text = (
                f"\n\nProcessed {datetime_to_discord_relative(dt=now, format='R')}."
            )

            full_message = header + "\n".join(messages) + footer_text
            if len(full_message) <= 2000:
                await report_channel.send(full_message)
            else:
                current_batch = []
                current_length = len(header) + len(footer_text)

                for msg in messages:
                    msg_length = len(msg) + 1  # +1 for newline
                    if current_length + msg_length > 2000:
                        await report_channel.send(
                            header + "\n".join(current_batch) + footer_text
                        )
                        current_batch = [msg]
                        current_length = len(header) + len(footer_text) + msg_length
                    else:
                        current_batch.append(msg)
                        current_length += msg_length

                if current_batch:
                    await report_channel.send(
                        header + "\n".join(current_batch) + footer_text
                    )

        await send_category_reports(
            "Rank Changes",
            rank_changes,
            icon,
            "Members who need rank adjustments based on their current points.",
        )
        await send_category_reports(
            "Probation Completed",
            probation_completed,
            find_emoji("Prospect"),
            f"Members who have completed their **{PROBATION_DAYS} day** probation period.",
        )
        await send_category_reports(
            "Rank Issues",
            issues,
            "⚠️",
        )

        await member_service.close()
