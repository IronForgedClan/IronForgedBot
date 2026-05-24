import asyncio
import io
import logging
from datetime import datetime
import time
from typing import Dict, List, Optional

import discord
from tabulate import tabulate

from ironforgedbot.common.activity_check import (
    check_bulk_activity,
    extract_overall_xp_gained,
)
from ironforgedbot.common.helpers import (
    format_duration,
    normalize_rsn,
    render_relative_time,
)
from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.config import CONFIG
from ironforgedbot.database.database import db
from ironforgedbot.services.service_factory import (
    create_absent_service,
)
from ironforgedbot.services.wom_service import (
    WomService,
    get_wom_service,
    WomServiceError,
    WomRateLimitError,
    WomTimeoutError,
)

logger = logging.getLogger(__name__)


@log_task_execution(logger)
async def job_check_activity(
    report_channel: discord.TextChannel,
) -> None:
    """
    Check member activity against rank-based thresholds and report inactive members.
    Uses role-based exemptions to exclude certain roles from activity checks.

    Args:
        report_channel: Discord channel to send reports to
    """
    execution_id = f"activity_check_{int(time.time())}"
    logger.info(f"Starting activity check execution: {execution_id}")

    start_time = time.perf_counter()
    logger.info(f"Activity check {execution_id} - Starting")

    try:
        async with db.get_session() as session:
            absent_service = create_absent_service(session)

            await report_channel.send("🧗 **Activity Check:** starting...")

            absentee_list = await absent_service.process_absent_members()
            known_absentees = [
                normalize_rsn(absentee.nickname) for absentee in absentee_list
            ]

            logger.debug(f"Known absentees: {known_absentees}")

            check_results = await _find_inactive_users(
                report_channel,
                known_absentees,
            )

            logger.debug(f"Activity check results: {check_results}")

            if check_results is None:
                logger.warning(
                    f"Activity check {execution_id} failed to fetch WOM data"
                )
                return

            if not check_results:
                logger.info(f"Activity check {execution_id} returned no results")
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

            ltm_gains = await _fetch_ltm_gains_for_members(
                inactive_results, report_channel
            )

            if ltm_gains is not None:
                table_rows = [
                    [
                        result.username,
                        result.discord_role,
                        f"{result.xp_gained:,}",
                        (
                            f"{ltm_gains[result.username.lower()]:,}"
                            if result.username.lower() in ltm_gains
                            else "N/A"
                        ),
                        (
                            render_relative_time(result.last_changed_at)
                            if result.last_changed_at
                            else "unknown"
                        ),
                    ]
                    for result in inactive_results
                ]
                headers = ["Member", "Role", "Gained", "LTM", "Last Updated"]
                colalign = ("left", "left", "right", "right", "right")
            else:
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
                headers = ["Member", "Role", "Gained", "Last Updated"]
                colalign = ("left", "left", "right", "right")

            sorted_results = _sort_results_safely(table_rows)
            result_table = tabulate(
                sorted_results,
                headers=headers,
                tablefmt="github",
                colalign=colalign,
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
        results: List of result rows. The XP gained column is always at index 2,
                 regardless of whether an LTM column is present.
                 Formats: [username, role, gained_xp, last_updated]
                       or [username, role, gained_xp, ltm_xp, last_updated]

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


async def _fetch_ltm_gains_for_members(
    inactive_results: List,
    report_channel: discord.TextChannel,
) -> Optional[Dict[str, int]]:
    """Fetch LTM XP gains for each inactive member individually.

    Only fetches data for members that failed the activity check, rather than
    the entire group. Per-member failures are non-fatal, that member shows
    N/A in the LTM column. A failure constructing the service sends a warning
    to the channel and returns an empty dict (column still shown, all N/A).

    Args:
        inactive_results: List of ActivityCheckResult for inactive members.
        report_channel: Discord channel for error reporting.

    Returns:
        Dict mapping lowercase username to LTM XP gained, or None if LTM is
        disabled (column omitted). Returns {} if LTM is enabled but all
        lookups fail (column still shown, all entries show N/A).
    """
    if not CONFIG.ltm_enabled:
        return None

    gains_map: Dict[str, int] = {}

    try:
        ltm_service = WomService(
            base_url=CONFIG.WOM_LTM_BASE_URL, group_id=CONFIG.WOM_LTM_GROUP_ID
        )
    except Exception as e:
        logger.warning(f"Failed to initialise LTM WOM service: {e}")
        await report_channel.send(
            "⚠️ LTM tracker unavailable. LTM column will show N/A for all members."
        )
        return gains_map

    async with ltm_service:
        for i, result in enumerate(inactive_results):
            try:
                player_gains = await ltm_service.get_player_monthly_gains(
                    result.username
                )
                xp = int(extract_overall_xp_gained(player_gains))
                if xp > 0:
                    gains_map[result.username.lower()] = xp
            except (WomServiceError, WomRateLimitError, WomTimeoutError) as e:
                logger.warning(
                    f"Failed to fetch LTM gains for {result.username}: {e}; showing N/A"
                )
            except Exception as e:
                logger.warning(
                    f"Unexpected error fetching LTM gains for {result.username}: {e}; showing N/A"
                )

            if i < len(inactive_results) - 1:
                await asyncio.sleep(0.1)

    logger.info(
        f"Fetched LTM gains for {len(gains_map)}/{len(inactive_results)} inactive members"
    )
    return gains_map


async def _find_inactive_users(
    report_channel: discord.TextChannel,
    absentees: List[str],
) -> Optional[List]:
    """
    Find inactive users based on WOM data and rank-based thresholds.
    Uses role-based exemptions to exclude certain roles from checks.

    Args:
        report_channel: Discord channel for error reporting
        absentees: List of known absent member usernames (lowercase)

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
