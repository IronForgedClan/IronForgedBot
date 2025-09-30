import asyncio
import io
import logging
from datetime import datetime
import time
from typing import Any, Dict, List, Optional

import discord
import wom
from tabulate import tabulate
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMembership

from ironforgedbot.common.helpers import (
    format_duration,
    render_relative_time,
)
from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.database.database import db
from ironforgedbot.services.service_factory import (
    create_absent_service,
    get_wom_client,
)
from ironforgedbot.services.wom_service import WomServiceError
from ironforgedbot.common.wom_role_mapping import (
    get_threshold_for_wom_role,
    get_display_name_for_wom_role,
    get_discord_role_for_wom_role,
)
from ironforgedbot.common.roles import is_exempt_from_activity_check

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

            results = await _find_inactive_users(
                report_channel,
                known_absentees,
                wom_limit,
            )

            logger.debug(results)

            if not results:
                logger.warning(f"Activity check {execution_id} returned no results")
                await report_channel.send(
                    "ℹ️ No inactive members found meeting the criteria."
                )
                return

            sorted_results = _sort_results_safely(results)
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
                f"Activity check {execution_id} completed successfully - found {len(results)} inactive members"
            )
            await report_channel.send(
                "## 🧗 Activity check\n"
                f"Ignoring **{len(known_absentees)}** absent members.\n"
                f"Found **{len(results)}** members that do not meet requirements.\n"
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


def _get_role_display_name(role: Optional[GroupRole]) -> str:
    """
    Get display name for a WOM group role.

    Args:
        role: WOM GroupRole enum value

    Returns:
        Clan relevant role name
    """
    return get_display_name_for_wom_role(role)


def _get_threshold_for_role(role: Optional[GroupRole]) -> int:
    """
    Get XP threshold for a given role using the new rank-based system.

    Args:
        role: WOM GroupRole enum value

    Returns:
        XP threshold for the role based on Discord rank mapping
    """
    return get_threshold_for_wom_role(role)


async def _find_inactive_users(
    report_channel: discord.TextChannel,
    absentees: List[str],
    wom_limit: int,
) -> Optional[List[List[str]]]:
    """
    Find inactive users based on WOM data and rank-based thresholds.
    Uses role-based exemptions to exclude certain roles from checks.

    Args:
        report_channel: Discord channel for error reporting
        absentees: List of known absent member usernames (lowercase)
        wom_limit: Number of records to fetch per API call

    Returns:
        List of inactive user data or None if error occurred
    """
    try:
        async with get_wom_client() as wom_client:
            try:
                logger.debug("Getting group details...")
                wom_group = await asyncio.wait_for(
                    wom_client.get_group_details(), timeout=30.0
                )
            except (WomServiceError, asyncio.TimeoutError) as e:
                error_msg = f"Failed to get group details: {e}"
                logger.error(error_msg)

                error_str = str(e).lower()
                if "rate limit" in error_str:
                    await report_channel.send(
                        "❌ WOM API rate limit exceeded. Please wait a few minutes before trying again."
                    )
                elif "timeout" in error_str or "connection" in error_str:
                    await report_channel.send(
                        "❌ WOM API connection timed out. Please check internet connectivity and try again."
                    )
                else:
                    await report_channel.send(
                        "❌ WOM API is currently unavailable. Please try again later."
                    )
                return None

            try:
                logger.debug("getting member monthly gains..")
                all_member_gains = await asyncio.wait_for(
                    wom_client.get_all_group_gains(
                        metric=Metric.Overall,
                        period=Period.Month,
                        limit=wom_limit,
                    ),
                    timeout=120.0,  # Longer timeout for pagination
                )
            except (WomServiceError, asyncio.TimeoutError) as e:
                error_msg = f"Failed to get group gains: {e}"
                logger.error(error_msg)

                error_str = str(e).lower()
                if "rate limit" in error_str:
                    await report_channel.send(
                        "❌ WOM API rate limit exceeded. Please wait a few minutes before trying again."
                    )
                elif "timeout" in error_str or "connection" in error_str:
                    await report_channel.send(
                        "❌ WOM API connection timed out. Please check internet connectivity and try again."
                    )
                else:
                    await report_channel.send(
                        "❌ WOM API error occurred. Please try again later."
                    )
                return None

            results = []
            for member_gains in all_member_gains:
                try:
                    inactive_member_data = _process_member_gains(
                        member_gains, wom_group, absentees
                    )
                    if inactive_member_data:
                        results.append(inactive_member_data)
                except Exception as process_error:
                    logger.warning(
                        f"Error processing member gains for {getattr(member_gains.player, 'username', 'unknown')}: {process_error}"
                    )

            return results

    except Exception as e:
        error_type = type(e).__name__
        if "JSON" in str(e) or "Decode" in error_type:
            logger.error(f"WOM API returned malformed JSON data: {e}")
            await report_channel.send(
                "❌ WOM API returned malformed data. This is likely a temporary issue with the WOM service."
            )
        else:
            logger.error(f"Unexpected error in _find_inactive_users: {e}")
            await report_channel.send(
                f"❌ Unexpected error processing WOM data: {error_type}"
            )
        return None


def _process_member_gains(
    member_gains,
    wom_group: GroupDetail,
    absentees: List[str],
) -> Optional[List[str]]:
    """
    Process individual member gains data to determine if they're inactive.
    Uses rank-based thresholds and role-based exemptions.

    Args:
        member_gains: WOM member gains data
        wom_group: WOM group details
        absentees: List of known absent member usernames (lowercase)

    Returns:
        List of member data if inactive, None otherwise
    """
    wom_member = _find_wom_member(wom_group, member_gains.player.id)

    if wom_member is None:
        return None

    if wom_member.player.username.lower() in absentees:
        return None

    # Check if member's Discord role is exempt from activity checks
    discord_role = get_discord_role_for_wom_role(wom_member.role)
    if discord_role and is_exempt_from_activity_check(discord_role):
        return None

    # Skip prospects
    if wom_member.role == GroupRole.Dogsbody:
        return None

    xp_threshold = _get_threshold_for_role(wom_member.role)

    if member_gains.data.gained >= xp_threshold:
        return None

    role_display = _get_role_display_name(wom_member.role)

    days_since_progression = "unknown"
    if wom_member.player.last_changed_at:
        days_since_progression = render_relative_time(wom_member.player.last_changed_at)

    return [
        member_gains.player.username,
        role_display,
        f"{int(member_gains.data.gained):,}",
        days_since_progression,
    ]


def _find_wom_member(group: GroupDetail, player_id: int) -> GroupMembership | None:
    for member in group.memberships:
        if member.player.id == player_id:
            return member

    return None
