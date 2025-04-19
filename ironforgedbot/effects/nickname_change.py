import logging
import time

import discord
from discord.errors import Forbidden

from ironforgedbot.common.helpers import format_duration, normalize_discord_string
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService, UniqueNicknameViolation

logger = logging.getLogger(__name__)


async def _rollback(
    report_channel: discord.TextChannel,
    discord_member: discord.Member,
    previous_nickname: str,
) -> bool:
    try:
        await discord_member.edit(
            nick=previous_nickname,
            reason="Nickname conflict in database, rolling back nickname",
        )
        return True
    except Forbidden:
        await report_channel.send(
            ":warning: The bot lacks permission to manage "
            f"{discord_member.mention}'s nickname."
        )
        return False


async def nickname_change(
    report_channel: discord.TextChannel, before: discord.Member, after: discord.Member
):
    if not check_member_has_role(after, ROLE.MEMBER):
        return

    start_time = time.perf_counter()
    async for session in db.get_session():
        service = MemberService(session)
        member = await service.get_member_by_discord_id(after.id)
        safe_new_nickname = normalize_discord_string(after.display_name)

        if not member:
            end_time = time.perf_counter()
            if not await _rollback(report_channel, after, before.display_name):
                return
            return await report_channel.send(
                f":warning: Name change detected: {text_bold(before.display_name)} → "
                f"{text_bold(safe_new_nickname)}. Member not found in database. "
                "Unable to save the change, rolling back. "
                f"Processed in **{format_duration(start_time, end_time)}**.",
            )

        if member.nickname == safe_new_nickname:
            return

        try:
            await service.change_nickname(member.id, safe_new_nickname)
        except UniqueNicknameViolation:
            conflicting_db_member = await service.get_member_by_nickname(
                safe_new_nickname
            )
            if not conflicting_db_member:
                if not await _rollback(report_channel, after, before.display_name):
                    return
                return await report_channel.send(
                    f":warning: Name change detected: {text_bold(before.display_name)} → "
                    f"{text_bold(safe_new_nickname)}. Name change was reverted "
                    "due to a **nickname conflict**. An error occured getting the "
                    "conflicting member's details."
                )

            conflicting_discord_member = report_channel.guild.get_member(
                conflicting_db_member.discord_id
            )

            if not await _rollback(report_channel, after, before.display_name):
                return

            end_time = time.perf_counter()
            return await report_channel.send(
                f":warning: Name change detected: {text_bold(before.display_name)} → "
                f"{text_bold(safe_new_nickname)}. Name change was reverted "
                f"due to a **nickname conflict**"
                + (
                    f" with {conflicting_discord_member.mention}. "
                    f"\n\n**U_ID:** {conflicting_db_member.id}\n"
                    f"**D_ID:** {conflicting_discord_member.id}"
                    if conflicting_discord_member
                    else "."
                )
                + f"\n\nProcessed in **{format_duration(start_time, end_time)}**.",
            )

        end_time = time.perf_counter()
        return await report_channel.send(
            f":information: Name change detected: {text_bold(before.display_name)} → "
            f"{text_bold(safe_new_nickname)}. Database updated. "
            f"Processed in **{format_duration(start_time, end_time)}**.",
        )
