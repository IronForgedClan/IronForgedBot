import logging
from typing import List, Tuple

import discord
from wom import GroupRole, Client

from ironforgedbot.common.helpers import (
    fit_log_lines_into_discord_messages,
    get_all_discord_members,
    normalize_discord_string,
)

logger = logging.getLogger(__name__)

IGNORED_ROLES = [GroupRole.Administrator, GroupRole.Helper]
IGNORED_USERS = ["x flavored"]


async def job_check_membership_discrepancies(
    guild: discord.Guild,
    report_channel: discord.TextChannel,
    wom_api_key: str,
    wom_group_id: int,
):
    await report_channel.send("Beginning membership discrepancy check...")

    discord_members = get_all_discord_members(guild)
    if len(discord_members) > 1:
        discord_members = [normalize_discord_string(s) for s in discord_members]

    wom_members, wom_ignore = await _get_valid_wom_members(
        wom_api_key, wom_group_id, report_channel
    )

    ignored = wom_ignore + IGNORED_USERS
    discord_members = [item for item in discord_members if item not in ignored]

    if (
        wom_members is None
        or len(wom_members) < 1
        or discord_members is None
        or len(discord_members) < 1
    ):
        await report_channel.send("Error fetching member list, aborting.")
        return

    await report_channel.send(
        f"## Members Found\nDiscord: **{len(discord_members)}** members\n"
        f"Wise Old Man: **{len(wom_members)}** members\n\n_Computing discrepancies..._"
    )

    only_discord = sorted(list(set(discord_members) - set(wom_members)))
    only_wom = sorted(list(set(wom_members) - set(discord_members)))

    only_discord.insert(0, "Members found only on discord:")
    only_wom.insert(0, "Members found only on wom:")

    discord_messages = fit_log_lines_into_discord_messages(only_discord + only_wom)
    for message in discord_messages:
        await report_channel.send(message)

    await report_channel.send(
        f"## Discrepancy Summary\nDiscord Only: **{len(only_discord) - 1}** members\n"
        f"Wise Old Man Only: **{len(only_wom) - 1}** members",
    )
    await report_channel.send("Finished membership discrepancy check.")


async def _get_valid_wom_members(
    wom_api_key: str, wom_group_id: int, updates_channel
) -> Tuple[List[str] | None, List[str]]:
    wom_client = Client(api_key=wom_api_key, user_agent="IronForged")
    await wom_client.start()

    wom_group_result = await wom_client.groups.get_details(wom_group_id)

    if wom_group_result.is_err:
        await updates_channel.send("Error fetching WOM group details.")
        return None, []

    wom_group = wom_group_result.unwrap()

    members: List[str] = []
    ignore_members: List[str] = []
    for member in wom_group.memberships:
        member_role = member.role
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
