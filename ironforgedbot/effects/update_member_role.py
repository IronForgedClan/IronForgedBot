import logging
import discord
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.roles import (
    ROLE,
    check_member_has_role,
    get_highest_privilage_role_from_member,
)
from ironforgedbot.database.database import db

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.services.member_service import MemberService


logger = logging.getLogger(__name__)


async def update_member_role(
    report_channel: discord.TextChannel, discord_member: discord.Member
):
    logger.debug(f"Processing role change for {discord_member.display_name}")
    role = get_highest_privilage_role_from_member(discord_member)

    if not role:
        await report_channel.send(
            f"**Error:** Role changed for {discord_member.mention}, "
            f"but role could not be determined."
        )
        return

    async with db.get_session() as session:
        service = MemberService(session)
        member = await service.get_member_by_discord_id(discord_member.id)

        if not member:
            await report_channel.send(
                f"**Error:** Role changed for {discord_member.mention}, "
                f"but database member not found. Role: {rank}."
            )
            return

        if member.role != role:
            await service.change_role(member.id, ROLE(role))
            await report_channel.send(
                f"**ℹ️ Role changed:** {discord_member.mention}'s role was changed to "
                f"**{RANK(rank)}**. Database updated."
            )
