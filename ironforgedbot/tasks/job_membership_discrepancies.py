import logging
from typing import List, Tuple

import discord
from wom import GroupRole

from ironforgedbot.common.helpers import (
    fit_log_lines_into_discord_messages,
    get_all_discord_members,
    normalize_discord_string,
)
from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.services.service_factory import get_wom_service
from ironforgedbot.services.wom_service import WomServiceError

logger = logging.getLogger(__name__)

IGNORED_ROLES = [GroupRole.Administrator, GroupRole.Helper]
IGNORED_USERS = ["x flavored"]


@log_task_execution(logger)
async def job_check_membership_discrepancies(
    guild: discord.Guild,
    report_channel: discord.TextChannel,
    wom_api_key: str,
    wom_group_id: int,
):
    def normalize_username(name: str) -> str:
        return name.lower().replace("-", " ").replace("_", " ")

    await report_channel.send("Beginning membership discrepancy check...")

    discord_members = get_all_discord_members(guild)
    wom_members, wom_ignore = await _get_valid_wom_members(
        wom_api_key, wom_group_id, report_channel
    )

    if len(discord_members) < 1:
        return await report_channel.send(
            "Error computing discord member list, aborting."
        )

    if not wom_members or len(wom_members) < 1:
        return await report_channel.send("Error computing wom member list, aborting.")

    ignored = wom_ignore + IGNORED_USERS
    logger.info(ignored)

    discord_members = [
        normalize_username(member)
        for member in discord_members
        if member not in ignored
    ]
    wom_members = [
        normalize_username(member) for member in wom_members if member not in ignored
    ]

    if (
        wom_members is None
        or len(wom_members) < 1
        or discord_members is None
        or len(discord_members) < 1
    ):
        return await report_channel.send("Error fetching member list, aborting.")

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
    try:
        async with get_wom_service(wom_api_key) as wom_service:
            try:
                wom_group = await wom_service.get_group_details(wom_group_id)
            except WomServiceError as e:
                await updates_channel.send("Error fetching WOM group details.")
                return None, []

            members: List[str] = []
            ignore_members: List[str] = []
            for member in wom_group.memberships:
                member_role = member.role
                member_rsn = normalize_discord_string(member.player.username)

                if member_role is None:
                    logger.info(f"{member_rsn} has no role, skipping.")
                    continue

                if member_role in IGNORED_ROLES:
                    logger.info(f"{member_rsn} has ignored role, skipping.")
                    if member_rsn not in IGNORED_USERS:
                        logger.info(f"adding {member_rsn} to ignored members list.")
                        ignore_members.append(member_rsn)
                    continue

                ignored = IGNORED_USERS + ignore_members
                if member_rsn not in ignored:
                    members.append(member_rsn)

            return members, ignore_members
    except Exception as e:
        logger.error(f"Unexpected error in _get_valid_wom_members: {e}")
        await updates_channel.send("Error fetching WOM group details.")
        return None, []
