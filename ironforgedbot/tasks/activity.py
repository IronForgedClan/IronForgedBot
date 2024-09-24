import datetime
import logging
from typing import Optional

import discord
import wom
from wom import GroupRole, Period, Skills
from wom.models import GroupDetail, GroupMembership

from ironforgedbot.common.helpers import (
    fit_log_lines_into_discord_messages,
    get_all_discord_members,
)
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError
from ironforgedbot.tasks import _send_discord_message_plain, can_start_task

logger = logging.getLogger(__name__)

DEFAULT_WOM_LIMIT = 50
MONTHLY_EXP_THRESHOLD = 100_000


async def job_check_activity_reminder(
    guild: discord.Guild,
    updates_channel_name: str,
):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Miss-configured task check_activity_reminder")
        return

    try:
        absentees = STORAGE.get_absentees()
    except StorageError as e:
        logger.error(f"Failed to read absentees list: {e}")
        return

    await _send_discord_message_plain(
        updates_channel,
        (
            f"REMINDER: Going to execute weekly activity check in one hour, "
            f"currently ignoring {len(absentees)} members. Update if necessary."
        ),
    )

    lines = []
    for absentee, date in absentees.items():
        lines.append(f"{absentee}, added on {date}")

    discord_messages = fit_log_lines_into_discord_messages(lines)
    for msg in discord_messages:
        await _send_discord_message_plain(updates_channel, msg)


async def job_check_activity(
    guild: discord.Guild,
    updates_channel_name: str,
    wom_api_key: str,
    wom_group_id: int,
):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Miss-configured task check_activity")
        return

    try:
        absentees = STORAGE.get_absentees()
    except StorageError as e:
        logger.error(f"Failed to read absentees list: {e}")
        return

    all_members = get_all_discord_members(guild)
    known_absentees = []
    for absentee in absentees.keys():
        known_absentees.append(absentee.lower())

    await _send_discord_message_plain(
        updates_channel,
        f"Starting weekly activity check for {len(all_members)} members "
        f"with the threshold {int(MONTHLY_EXP_THRESHOLD / 1_000)}k/month",
    )

    results = await _find_inactive_users(
        wom_api_key, wom_group_id, updates_channel, known_absentees
    )

    if results is None:
        return

    results = {k: v for k, v in sorted(results.items(), key=lambda item: item[1])}
    discord_messages = fit_log_lines_into_discord_messages(results.keys())
    for msg in discord_messages:
        await _send_discord_message_plain(updates_channel, msg)

    await _send_discord_message_plain(
        updates_channel,
        f"Finished weekly activity check, found {len(results)} under-performers "
        f"and {len(absentees)} known absentees",
    )


async def _find_inactive_users(
    wom_api_key: str, wom_group_id: int, updates_channel, absentees: list[str]
):
    wom_client = wom.Client(api_key=wom_api_key, user_agent="IronForged")
    await wom_client.start()
    is_done = False
    offset = 0
    results = {}
    wom_grop_result = await wom_client.groups.get_details(wom_group_id)
    if wom_grop_result.is_ok:
        wom_group = wom_grop_result.unwrap()
    else:
        message = f"Got error, fetching WOM group: {wom_grop_result.unwrap_err()}"
        logger.error(message)
        await updates_channel.send(content=message)
        return None

    while not is_done:
        result = await wom_client.groups.get_gains(
            wom_group_id,
            metric=Skills.Overall,
            period=Period.Month,
            limit=DEFAULT_WOM_LIMIT,
            offset=offset,
        )
        if result.is_ok:
            offset += DEFAULT_WOM_LIMIT
            details = result.unwrap()
            for member_gains in details:
                if member_gains.data.gained < MONTHLY_EXP_THRESHOLD:
                    wom_member = _find_wom_member(wom_group, member_gains.player.id)
                    if wom_member is None:
                        continue

                    if wom_member.player.username.lower() in absentees:
                        continue

                    if wom_member.membership.role is None:
                        role = "Unknown"
                    elif wom_member.membership.role == GroupRole.Helper:
                        role = "Alt"
                    elif wom_member.membership.role == GroupRole.Dogsbody:
                        continue
                    elif wom_member.membership.role == GroupRole.Gold:
                        role = "Staff"
                    elif wom_member.membership.role == GroupRole.Collector:
                        role = "Mod"
                    else:
                        role = str(wom_member.membership.role).title()

                    days_since_progression = (
                        datetime.datetime.now() - member_gains.player.last_changed_at
                    ).days
                    data = (
                        f"{member_gains.player.username} ({role}) gained {int(member_gains.data.gained / 1_000)}k, "
                        f"last progressed {days_since_progression} days ago "
                        f"({member_gains.player.last_changed_at.strftime('%Y-%m-%d')})"
                    )
                    results[data] = member_gains.data.gained

            if len(details) < DEFAULT_WOM_LIMIT:
                is_done = True
        else:
            message = f"Got error, fetching gains from WOM: {result.unwrap_err()}"
            logger.error(message)
            await updates_channel.send(content=message)
            return None

    await wom_client.close()
    return results


def _find_wom_member(group: GroupDetail, player_id: int) -> Optional[GroupMembership]:
    for member in group.memberships:
        if member.player.id == player_id:
            return member

    return None
