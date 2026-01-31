import logging

import discord

from ironforgedbot.common.helpers import (
    find_emoji,
    get_discord_role,
)
from ironforgedbot.common.roles import ROLE, PROSPECT_ROLE_NAME, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


async def add_prospect_role(
    report_channel: discord.TextChannel, member: discord.Member
):
    logger.debug(f"Processing Prospect role addition for {member.display_name}")

    report_content = (
        f"{find_emoji('Prospect')} {member.mention} has been "
        f"given the {text_bold(PROSPECT_ROLE_NAME)} role."
    )
    report_message = await report_channel.send(report_content + " Fixing roles...")
    roles_removed = ""
    roles_added = ""

    prospect_role = get_discord_role(report_channel.guild, PROSPECT_ROLE_NAME)
    if prospect_role is None:
        raise ValueError("Unable to access Prospect role value")

    async with db.get_session() as session:
        service = MemberService(session)
        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_prospect=True)
            logger.debug(f"Set is_prospect=True for {member.display_name}")

    if check_member_has_role(member, ROLE.APPLICANT):
        applicant_role = get_discord_role(report_channel.guild, ROLE.APPLICANT)
        if applicant_role is None:
            raise ValueError("Unable to access Applicant role values")

        roles_removed += f" {text_bold(ROLE.APPLICANT)},"
        await member.remove_roles(
            applicant_role, reason="Prospect: remove Applicant role"
        )

    if check_member_has_role(member, ROLE.GUEST):
        guest_role = get_discord_role(report_channel.guild, ROLE.GUEST)
        if guest_role is None:
            raise ValueError("Unable to access Guest role values")

        roles_removed += f" {text_bold(ROLE.GUEST)},"
        await member.remove_roles(guest_role, reason="Prospect: remove Guest role")

    if not check_member_has_role(member, ROLE.MEMBER):
        member_role = get_discord_role(report_channel.guild, ROLE.MEMBER)
        if member_role is None:
            raise ValueError("Unable to access Member role value")

        roles_added += f" {text_bold(ROLE.MEMBER)},"
        await member.add_roles(member_role, reason="Prospect: adding Member role")

    msg = f" Added roles: {roles_added[:-1]}." if len(roles_added) > 0 else ""
    msg += f" Removed roles: {roles_removed[:-1]}." if len(roles_removed) > 0 else ""
    await report_message.edit(content=report_content + msg)
