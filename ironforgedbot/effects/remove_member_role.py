import discord
import time

from discord.errors import Forbidden
from ironforgedbot.common.helpers import format_duration, get_discord_role
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE, is_member_banned
from ironforgedbot.common.text_formatters import text_ul
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.database.database import db


async def remove_member_role(
    report_channel: discord.TextChannel, member: discord.Member
):
    start_time = time.perf_counter()
    member_roles = set(role.name for role in member.roles)
    roles_to_remove = RANK.list() + ROLE.list() + GOD_ALIGNMENT.list()
    is_banned = is_member_banned(member)

    roles_removed = []
    for role_name in roles_to_remove:
        if role_name == ROLE.BANNED:
            continue

        if role_name in member_roles:
            role = get_discord_role(report_channel.guild, role_name)

            if not role:
                raise ValueError(f"Unable to get role {role_name}")

            roles_removed.append(role)

    if len(roles_removed) > 0:
        try:
            await member.remove_roles(
                *roles_removed, reason="Member removed. Cleaning up roles."
            )
        except Forbidden:
            return await report_channel.send(
                f":warning: The bot lacks permission to manage {member.mention}'s roles."
            )

    async with db.get_session() as session:
        service = MemberService(session)
        db_member = await service.get_member_by_discord_id(member.id)

        if not db_member:
            return await report_channel.send(
                f":warning: Member {member.mention} has been removed, but "
                "cannot be found in the database."
            )

        await service.disable_member(db_member.id)

        end_time = time.perf_counter()

        roles_message = (
            f" Removed the following **discord roles** from this user:\n{text_ul([r.name for r in roles_removed])}"
            if len(roles_removed) > 0
            else ""
        )

        if is_banned:
            await report_channel.send(
                f":x: **Member banned:** {member.mention} has been removed. "
                f"Disabled member in database.{roles_message}"
                f"Processed in **{format_duration(start_time, end_time)}**.",
            )
            return

        await report_channel.send(
            f":x: **Member disabled:** {member.mention} has been removed. "
            f"Disabled member in database.{roles_message}"
            f"Processed in **{format_duration(start_time, end_time)}**.",
        )
