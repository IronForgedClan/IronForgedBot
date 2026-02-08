import logging
import time
from typing import Optional

from discord.errors import Forbidden
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import format_duration, normalize_discord_string
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService, UniqueNicknameViolation

logger = logging.getLogger(__name__)


class NicknameChangeHandler(BaseMemberUpdateHandler):
    priority = 50

    @property
    def name(self) -> str:
        return "NicknameChange"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return context.nickname_changed and check_member_has_role(
            context.after, ROLE.MEMBER
        )

    async def _rollback(
        self,
        context: MemberUpdateContext,
        previous_nickname: str,
    ) -> bool:
        try:
            await context.after.edit(
                nick=previous_nickname,
                reason="Nickname conflict in database, rolling back nickname",
            )
            member_update_emitter.suppress_next_for(context.discord_id)
            return True
        except Forbidden:
            await context.report_channel.send(
                f":warning: The bot lacks permission to manage "
                f"{context.after.mention}'s nickname."
            )
            return False

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        start_time = time.perf_counter()
        before = context.before
        after = context.after

        member = await service.get_member_by_discord_id(after.id)
        safe_new_nickname = normalize_discord_string(after.display_name)

        if not member:
            end_time = time.perf_counter()
            if not await self._rollback(context, before.display_name):
                return None
            return (
                f":warning: Name change detected: {text_bold(before.display_name)} → "
                f"{text_bold(safe_new_nickname)}. Member not found in database. "
                f"Unable to save the change, rolling back. "
                f"Processed in **{format_duration(start_time, end_time)}**."
            )

        if member.nickname == safe_new_nickname:
            return None

        try:
            await service.change_nickname(member.id, safe_new_nickname)
        except UniqueNicknameViolation:
            return await self._handle_nickname_conflict(
                context, service, before.display_name, safe_new_nickname, start_time
            )

        end_time = time.perf_counter()
        return (
            f":information: Name change detected: {text_bold(before.display_name)} → "
            f"{text_bold(safe_new_nickname)}. Database updated. "
            f"Processed in **{format_duration(start_time, end_time)}**."
        )

    async def _handle_nickname_conflict(
        self,
        context: MemberUpdateContext,
        service: MemberService,
        previous_name: str,
        new_name: str,
        start_time: float,
    ) -> Optional[str]:
        conflicting_db_member = await service.get_member_by_nickname(new_name)

        if not conflicting_db_member:
            if not await self._rollback(context, previous_name):
                return None
            return (
                f":warning: Name change detected: {text_bold(previous_name)} → "
                f"{text_bold(new_name)}. Name change was reverted "
                "due to a **nickname conflict**. An error occured getting the "
                "conflicting member's details."
            )

        conflicting_discord_member = context.report_channel.guild.get_member(
            conflicting_db_member.discord_id
        )

        if not await self._rollback(context, previous_name):
            return None

        end_time = time.perf_counter()

        conflict_info = ""
        if conflicting_discord_member:
            conflict_info = (
                f" with {conflicting_discord_member.mention}. "
                f"\n\n**U_ID:** {conflicting_db_member.id}\n"
                f"**D_ID:** {conflicting_discord_member.id}"
            )
        else:
            conflict_info = "."

        return (
            f":warning: Name change detected: {text_bold(previous_name)} → "
            f"{text_bold(new_name)}. Name change was reverted "
            f"due to a **nickname conflict**{conflict_info}"
            f"\n\nProcessed in **{format_duration(start_time, end_time)}**."
        )


member_update_emitter.register(NicknameChangeHandler())
