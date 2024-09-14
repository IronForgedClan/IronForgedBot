import asyncio
import logging
from typing import List, TypedDict
import discord
import wom

from wom import GroupRole
from ironforgedbot.common.helpers import (
    get_all_discord_members,
    fit_log_lines_into_discord_messages,
)
from ironforgedbot.tasks import can_start_task, _send_discord_message_plain

logger = logging.getLogger(__name__)

IGNORED_ROLES = [GroupRole.Administrator]
IGNORED_USERS = ["x flavored"]

VALID_WOM_ROLES = [
    GroupRole.Dogsbody,
    GroupRole.Iron,
    GroupRole.Mithril,
    GroupRole.Adamant,
    GroupRole.Rune,
    GroupRole.Dragon,
    GroupRole.Legend,
    GroupRole.Myth,
    GroupRole.Helper,
    GroupRole.Gnome_child,
    GroupRole.Gold,
    GroupRole.Collector,
    GroupRole.Sergeant,
    GroupRole.Colonel,
    GroupRole.Marshal,
    GroupRole.Deputy_owner,
    GroupRole.Owner,
]


async def job_check_membership_discrepancies(
    guild: discord.Guild,
    updates_channel_name: str,
    wom_api_key: str,
    wom_group_id: int,
    loop: asyncio.BaseEventLoop,
):
    updates_channel = can_start_task(guild, updates_channel_name)
    if updates_channel is None:
        logger.error("Miss-configured task job_check_membership_discrepancies")
        return

    asyncio.run_coroutine_threadsafe(
        _send_discord_message_plain(
            updates_channel, "Beginning membership discrepancy check..."
        ),
        loop,
    )

    discord_members = get_all_discord_members(guild)
    get_wom_members = asyncio.run_coroutine_threadsafe(
        _get_valid_wom_members(wom_api_key, wom_group_id, updates_channel),
        loop,
    )
    wom_members = get_wom_members.result()

    if (
        wom_members is None
        or len(wom_members) < 1
        or discord_members is None
        or len(discord_members) < 1
    ):
        asyncio.run_coroutine_threadsafe(
            _send_discord_message_plain(
                updates_channel, "Error fetching member list, aborting."
            ),
            loop,
        )
        return

    only_discord = list(set(discord_members) - set(wom_members))
    only_wom = list(set(wom_members) - set(discord_members))

    only_discord.insert(0, "Members found only on discord:")
    only_wom.insert(0, "Members found only on wom:")

    discord_messages = fit_log_lines_into_discord_messages(only_discord + only_wom)
    for msg in discord_messages:
        asyncio.run_coroutine_threadsafe(
            _send_discord_message_plain(updates_channel, msg), loop
        )

    asyncio.run_coroutine_threadsafe(
        _send_discord_message_plain(
            updates_channel,
            f"Finished weekly membership discrepancy check.\nFound **{len(only_discord) -1}** members "
            f"only on discord, and **{len(only_wom) -1}** members only on wom.",
        ),
        loop,
    )


async def _get_valid_wom_members(
    wom_api_key: str, wom_group_id: int, updates_channel
) -> List[str] | None:
    wom_client = wom.Client(api_key=wom_api_key, user_agent="IronForged")
    await wom_client.start()

    wom_group_result = await wom_client.groups.get_details(wom_group_id)
    if wom_group_result.is_ok:
        wom_group = wom_group_result.unwrap()
    else:
        message = f"Got error, fetching WOM group: {wom_group_result.unwrap_err()}"
        logger.error(message)
        await updates_channel.send(content=message)
        return None

    result: List[str] = []
    for member in wom_group.memberships:
        member_role = member.membership.role
        member_rsn = member.player.username
        if (
            member_role is not None
            and member_role not in IGNORED_ROLES
            and member_rsn not in IGNORED_USERS
            and member_role in VALID_WOM_ROLES
        ):
            result.append(member_rsn)

    await wom_client.close()
    return result
