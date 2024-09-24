import logging
from typing import List, Tuple

import discord
import wom
from wom import GroupRole

from ironforgedbot.common.helpers import (
    fit_log_lines_into_discord_messages,
    get_all_discord_members,
)
from ironforgedbot.tasks import _send_discord_message_plain, can_start_task

logger = logging.getLogger(__name__)

IGNORED_ROLES = [GroupRole.Administrator, GroupRole.Helper]
IGNORED_USERS = ["x flavored"]


async def job_check_membership_discrepancies(
    guild: discord.Guild,
    updates_channel_name: str,
    wom_api_key: str,
    wom_group_id: int,
):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Bad configuration job_check_membership_discrepancies")
        return

    await _send_discord_message_plain(
        updates_channel, "Beginning membership discrepancy check..."
    )

    discord_members = get_all_discord_members(guild)
    if len(discord_members) > 1:
        discord_members = [s.lower() for s in discord_members]

    wom_members, wom_ignore = await _get_valid_wom_members(
        wom_api_key, wom_group_id, updates_channel
    )

    ignored = wom_ignore + IGNORED_USERS
    discord_members = [item for item in discord_members if item not in ignored]

    if (
        wom_members is None
        or len(wom_members) < 1
        or discord_members is None
        or len(discord_members) < 1
    ):
        await _send_discord_message_plain(
            updates_channel, "Error fetching member list, aborting."
        )
        return

    only_discord = sorted(list(set(discord_members) - set(wom_members)))
    only_wom = sorted(list(set(wom_members) - set(discord_members)))

    only_discord.insert(0, "Member(s) found only on discord:")
    only_wom.insert(0, "Member(s) found only on wom:")

    discord_messages = fit_log_lines_into_discord_messages(only_discord + only_wom)

    await _return_output(updates_channel, discord_messages)

    await _send_finished_message(
        updates_channel, len(only_discord) - 1, len(only_wom) - 1
    )


async def _send_finished_message(updates_channel, found_discord: int, found_wom: int):
    await _send_discord_message_plain(
        updates_channel,
        f"Finished weekly membership discrepancy check.\nFound **{found_discord}** member(s) "
        f"only on discord, and **{found_wom}** member(s) only on wom.",
    )


async def _return_output(updates_channel, messages):
    for message in messages:
        await updates_channel.send(content=message)

    return True


async def _get_valid_wom_members(
    wom_api_key: str, wom_group_id: int, updates_channel
) -> Tuple[List[str] | None, List[str]]:
    wom_client = wom.Client(api_key=wom_api_key, user_agent="IronForged")
    await wom_client.start()

    wom_group_result = await wom_client.groups.get_details(wom_group_id)
    if wom_group_result.is_ok:
        wom_group = wom_group_result.unwrap()
    else:
        message = f"Got error, fetching WOM group: {wom_group_result.unwrap_err()}"
        logger.error(message)
        await updates_channel.send(content=message)
        return None, []

    members: List[str] = []
    ignore_members: List[str] = []
    for member in wom_group.memberships:
        member_role = member.membership.role
        member_rsn = member.player.username

        if member_role is None:
            continue

        if member_role in IGNORED_ROLES:
            if member_rsn not in IGNORED_USERS:
                ignore_members.append(member_rsn)
            continue

        if member_rsn not in IGNORED_USERS or member_rsn not in ignore_members:
            members.append(member_rsn)

    await wom_client.close()
    return members, ignore_members
