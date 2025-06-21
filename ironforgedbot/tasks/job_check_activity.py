import logging

import discord
import wom
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMembership

from ironforgedbot.common.helpers import (
    fit_log_lines_into_discord_messages,
    render_relative_time,
)
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)

DEFAULT_WOM_LIMIT = 50
IRON_EXP_THRESHOLD = 150_000
MITHRIL_EXP_THRESHOLD = 300_000
RUNE_EXP_THRESHOLD = 500_000


async def job_check_activity_reminder(report_channel: discord.TextChannel):
    try:
        absentees = await STORAGE.get_absentees()
    except StorageError as e:
        logger.error(f"Failed to read absentees list: {e}")
        await report_channel.send("Failed to read absentee list")
        return

    await report_channel.send(
        (
            f"**REMINDER:**\nExecuting activity check in one hour.\n"
            f"Ignoring **{len(absentees)}** member(s). Update storage if necessary."
        )
    )

    lines = []
    for absentee, date in absentees.items():
        lines.append(f"{absentee} [Added: {date}]")

    discord_messages = fit_log_lines_into_discord_messages(lines)
    for msg in discord_messages:
        await report_channel.send(msg)


async def job_check_activity(
    report_channel: discord.TextChannel,
    wom_api_key: str,
    wom_group_id: int,
):
    try:
        absentees = await STORAGE.get_absentees()
    except StorageError as e:
        logger.error(f"Failed to read absentees list: {e}")
        return

    await report_channel.send("Beginning activity check...")

    known_absentees = []
    for absentee in absentees.keys():
        known_absentees.append(absentee.lower())

    await report_channel.send(
        f"Found **{len(known_absentees)}** absent member(s).\n"
        f"Iron threshold: **{IRON_EXP_THRESHOLD:,}** xp/month.\n"
        f"Mithril+ threshold: **{MITHRIL_EXP_THRESHOLD:,}** xp/month.\n"
        f"Rune+ threshold: **{RUNE_EXP_THRESHOLD:,}** xp/month.",
    )

    results = await _find_inactive_users(
        wom_api_key, wom_group_id, report_channel, known_absentees
    )

    if results is None:
        return

    results = {k: v for k, v in sorted(results.items(), key=lambda item: item[1])}
    discord_messages = fit_log_lines_into_discord_messages(results.keys())
    for msg in discord_messages:
        await report_channel.send(msg)

    await report_channel.send(
        f"Found **{len(results)}** member(s) that do not meet requirements."
    )
    await report_channel.send("Finished activity check.")


async def _find_inactive_users(
    wom_api_key: str,
    wom_group_id: int,
    report_channel: discord.TextChannel,
    absentees: list[str],
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
        await report_channel.send(content=message)
        return None

    while not is_done:
        result = await wom_client.groups.get_gains(
            wom_group_id,
            metric=Metric.Overall,
            period=Period.Month,
            limit=DEFAULT_WOM_LIMIT,
            offset=offset,
        )
        if result.is_ok:
            offset += DEFAULT_WOM_LIMIT
            details = result.unwrap()
            for member_gains in details:
                wom_member = _find_wom_member(wom_group, member_gains.player.id)

                if wom_member is None:
                    continue
                if wom_member.player.username.lower() in absentees:
                    continue

                match wom_member.role:
                    case GroupRole.Iron:
                        xp_threshold = IRON_EXP_THRESHOLD
                    case GroupRole.Mithril | GroupRole.Adamant:
                        xp_threshold = MITHRIL_EXP_THRESHOLD
                    case _:
                        xp_threshold = RUNE_EXP_THRESHOLD

                if member_gains.data.gained < xp_threshold:
                    if wom_member.role is None:
                        role = "Unknown"
                    elif wom_member.role == GroupRole.Helper:
                        role = "Alt"
                    elif wom_member.role == GroupRole.Dogsbody:
                        continue
                    elif wom_member.role == GroupRole.Gold:
                        role = "Staff"
                    elif wom_member.role == GroupRole.Collector:
                        role = "Mod"
                    else:
                        role = str(wom_member.role).title()

                    if wom_member.player.last_changed_at:
                        days_since_progression = render_relative_time(
                            wom_member.player.last_changed_at
                        )
                    else:
                        days_since_progression = "unknown"

                    data = (
                        f"{member_gains.player.username} ({role}) gained {int(member_gains.data.gained / 1_000)}k, "
                        f"last progressed {days_since_progression} "
                        f"({member_gains.player.last_changed_at.strftime('%Y-%m-%d')})"
                    )
                    results[data] = member_gains.data.gained

            if len(details) < DEFAULT_WOM_LIMIT:
                is_done = True
        else:
            message = f"Got error, fetching gains from WOM: {result.unwrap_err()}"
            logger.error(message)
            await report_channel.send(content=message)
            return None

    await wom_client.close()
    return results


def _find_wom_member(group: GroupDetail, player_id: int) -> GroupMembership | None:
    for member in group.memberships:
        if member.player.id == player_id:
            return member

    return None
