import io
import logging
from datetime import datetime
import time

import discord
import wom
from tabulate import tabulate
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMembership

from ironforgedbot.common.helpers import (
    format_duration,
    render_relative_time,
)
from ironforgedbot.database.database import db
from ironforgedbot.services.absent_service import AbsentMemberService

logger = logging.getLogger(__name__)

DEFAULT_WOM_LIMIT = 50
IRON_EXP_THRESHOLD = 150_000
MITHRIL_EXP_THRESHOLD = 300_000
RUNE_EXP_THRESHOLD = 500_000


async def job_check_activity(
    report_channel: discord.TextChannel,
    wom_api_key: str,
    wom_group_id: int,
):
    start_time = time.perf_counter()
    async for session in db.get_session():
        absent_service = AbsentMemberService(session)
        absentee_list = await absent_service.process_absent_members()

        known_absentees = []
        for absentee in absentee_list:
            known_absentees.append(absentee.nickname.lower())

        results = await _find_inactive_users(
            wom_api_key, wom_group_id, report_channel, known_absentees
        )

        if not results:
            logger.error("Activity check empty")
            return

        sorted_results = sorted(results, key=lambda row: int(row[2].replace(",", "")))
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
        await report_channel.send(
            "## 🧗 Activity check\n"
            f"Ignoring **{len(known_absentees)}** absent members.\n"
            f"Found **{len(results)}** members that do not meet requirements.\n"
            f"Processed in **{format_duration(start_time, end_time)}**.",
            file=discord_file,
        )


async def _find_inactive_users(
    wom_api_key: str,
    wom_group_id: int,
    report_channel: discord.TextChannel,
    absentees: list[str],
) -> list[list] | None:
    wom_client = wom.Client(api_key=wom_api_key, user_agent="IronForged")
    await wom_client.start()

    is_done = False
    offset = 0
    results = []
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

                if wom_member.role == GroupRole.Dogsbody:
                    continue

                match wom_member.role:
                    case GroupRole.Iron:
                        xp_threshold = IRON_EXP_THRESHOLD
                    case GroupRole.Mithril | GroupRole.Adamant:
                        xp_threshold = MITHRIL_EXP_THRESHOLD
                    case _:
                        xp_threshold = RUNE_EXP_THRESHOLD

                if member_gains.data.gained < xp_threshold:
                    if not wom_member.role:
                        role = "Unknown"
                    elif wom_member.role == GroupRole.Helper:
                        role = "Alt"
                    elif wom_member.role == GroupRole.Collector:
                        role = "Moderator"
                    elif wom_member.role == GroupRole.Administrator:
                        role = "Admin"
                    elif wom_member.role in [
                        GroupRole.Colonel,
                        GroupRole.Brigadier,
                        GroupRole.Admiral,
                        GroupRole.Marshal,
                    ]:
                        role = "Staff"
                    elif wom_member.role in [GroupRole.Deputy_owner, GroupRole.Owner]:
                        role = "Owner"
                    else:
                        role = str(wom_member.role).title()

                    days_since_progression = "unknown"
                    if wom_member.player.last_changed_at:
                        days_since_progression = render_relative_time(
                            wom_member.player.last_changed_at
                        )

                    results.append(
                        [
                            member_gains.player.username,
                            role,
                            f"{int(member_gains.data.gained):,}",
                            days_since_progression,
                        ]
                    )

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
