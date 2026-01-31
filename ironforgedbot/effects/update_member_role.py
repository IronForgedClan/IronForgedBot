import logging
import discord
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.roles import (
    ROLE,
    check_member_has_role,
    get_highest_privilage_role_from_member,
    has_booster_role,
    has_prospect_role,
    has_blacklisted_role,
    is_member_banned_by_role,
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
                f"but database member not found. Role: {role}."
            )
            return

        if member.role != role:
            await service.change_role(member.id, ROLE(role), admin_id=None)
            await report_channel.send(
                f"**ℹ️ Role changed:** {discord_member.mention}'s role was changed to "
                f"**{role}**. Database updated."
            )

        is_booster = has_booster_role(discord_member)
        is_prospect = has_prospect_role(discord_member)
        is_blacklisted = has_blacklisted_role(discord_member)
        is_banned = is_member_banned_by_role(discord_member)

        flags_changed = (
            member.is_booster != is_booster
            or member.is_prospect != is_prospect
            or member.is_blacklisted != is_blacklisted
            or member.is_banned != is_banned
        )

        if flags_changed:
            await service.update_member_flags(
                member.id,
                is_booster=is_booster,
                is_prospect=is_prospect,
                is_blacklisted=is_blacklisted,
                is_banned=is_banned,
            )
            logger.debug(
                f"Updated flags for {discord_member.display_name}: "
                f"booster={is_booster}, prospect={is_prospect}, "
                f"blacklisted={is_blacklisted}, banned={is_banned}"
            )
