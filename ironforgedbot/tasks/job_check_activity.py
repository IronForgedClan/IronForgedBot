import io
import logging
from datetime import datetime
import time
from typing import List

import discord
from tabulate import tabulate

from ironforgedbot.common.activity_check import check_bulk_activity
from ironforgedbot.common.helpers import (
    format_duration,
    render_relative_time,
)
from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.database.database import db
from ironforgedbot.services.service_factory import (
    create_absent_service,
)
from ironforgedbot.services.wom_service import (
    get_wom_service,
    WomServiceError,
    WomRateLimitError,
    WomTimeoutError,
)

logger = logging.getLogger(__name__)

DEFAULT_WOM_LIMIT = 50


@log_task_execution(logger)
async def job_check_activity(
    report_channel: discord.TextChannel,
    wom_limit: int = DEFAULT_WOM_LIMIT,
) -> None:
    """
    Check member activity against rank-based thresholds and report inactive members.
    Uses role-based exemptions to exclude certain roles from activity checks.

    Args:
        report_channel: Discord channel to send reports to
        wom_limit: Number of records to fetch per API call
    """
    execution_id = f"activity_check_{int(time.time())}"
    logger.info(f"Starting activity check execution: {execution_id}")

    start_time = time.perf_counter()
    logger.info(f"Activity check {execution_id} - Starting with limit {wom_limit}")

    try:
        async with db.get_session() as session:
            absent_service = create_absent_service(session)

            await report_channel.send("🧗 **Activity Check:** starting...")

            absentee_list = await absent_service.process_absent_members()
            known_absentees = [absentee.nickname.lower() for absentee in absentee_list]

            logger.debug(known_absentees)

            check_results = await _find_inactive_users(
                report_channel,
                known_absentees,
                wom_limit,
            )

            logger.debug(check_results)

            if not check_results:
                logger.warning(f"Activity check {execution_id} returned no results")
                await report_channel.send(
                    "ℹ️ No inactive members found meeting the criteria."
                )
                return

            inactive_results = [
                r for r in check_results if not r.is_active and r.skip_reason is None
            ]

            if not inactive_results:
                logger.info(f"Activity check {execution_id} - all members are active")
                await report_channel.send("✅ All members meet activity requirements!")
                return

            table_rows = [
                [
                    result.username,
                    result.discord_role,
                    f"{result.xp_gained:,}",
                    (
                        render_relative_time(result.last_changed_at)
                        if result.last_changed_at
                        else "unknown"
                    ),
                ]
                for result in inactive_results
            ]

            sorted_results = _sort_results_safely(table_rows)
            result_table = tabulate(
                sorted_results,
                headers=["Member", "Role", "Gained", "Last Updated"],
                tablefmt="github",
                colalign=("left", "left", "right", "right"),
            )

            discord_file = discord.File(
                fp=io.BytesIO(result_table.encode("utf-8")),
                filename=f"activity_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            )

            end_time = time.perf_counter()
            logger.info(
                f"Activity check {execution_id} completed successfully - found {len(inactive_results)} inactive members"
            )
            await report_channel.send(
                "## 🧗 Activity check\n"
                f"Ignoring **{len(known_absentees)}** absent members.\n"
                f"Found **{len(inactive_results)}** members that do not meet requirements.\n"
                f"Processed in **{format_duration(start_time, end_time)}**.",
                file=discord_file,
            )
    except Exception as e:
        logger.error(f"Activity check {execution_id} failed: {type(e).__name__}: {e}")
        await report_channel.send(
            f"⚠️ Activity check failed (ID: {execution_id}): {type(e).__name__}: {e}"
        )
        raise


def _sort_results_safely(results: List[List[str]]) -> List[List[str]]:
    """
    Safely sort results by XP gained, handling malformed data.

    Args:
        results: List of result rows with format [username, role, gained_xp, last_updated]

    Returns:
        Sorted results list
    """

    def safe_int_extract(row: List[str]) -> int:
        try:
            return int(row[2].replace(",", ""))
        except (ValueError, IndexError):
            logger.warning(f"Malformed XP data in row: {row}")
            return 0

    return sorted(results, key=safe_int_extract)


async def _find_inactive_users(
    report_channel: discord.TextChannel,
    absentees: List[str],
    wom_limit: int,
):
    """
    Find inactive users based on WOM data and rank-based thresholds.
    Uses role-based exemptions to exclude certain roles from checks.

    Args:
        report_channel: Discord channel for error reporting
        absentees: List of known absent member usernames (lowercase)
        wom_limit: Number of records to fetch per API call

    Returns:
        List of ActivityCheckResult objects or None if error occurred
    """
    try:
        async with get_wom_service() as wom_service:
            try:
                logger.debug("Getting monthly activity data...")
                wom_group, all_member_gains = (
                    await wom_service.get_monthly_activity_data()
                )

            except WomRateLimitError:
                await report_channel.send(
                    "❌ WOM API rate limit exceeded. Please wait a few minutes before trying again."
                )
                return None
            except WomTimeoutError:
                await report_channel.send(
                    "❌ WOM API connection timed out. Please check internet connectivity and try again."
                )
                return None
            except WomServiceError:
                await report_channel.send(
                    "❌ WOM API is currently unavailable. Please try again later."
                )
                return None

            results = await check_bulk_activity(wom_group, all_member_gains, absentees)
            return results

    except Exception as e:
        logger.error(f"Unexpected error in _find_inactive_users: {e}")
        await report_channel.send(
            "❌ Unexpected error processing WOM data. Please try again later."
        )
        return None
