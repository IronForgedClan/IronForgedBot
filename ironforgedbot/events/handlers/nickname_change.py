import logging
from typing import Optional

from discord.errors import Forbidden
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.roles import ROLE, check_member_has_role
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
        before = context.before
        after = context.after

        member = await service.get_member_by_discord_id(after.id)
        safe_new_nickname = normalize_discord_string(after.display_name)

        if not member:
            if not await self._rollback(context, before.display_name):
                return None
            return (
                f":warning: **Name changed:** {after.mention} "
                f"**{before.display_name}** → **{safe_new_nickname}**. "
                f"Member not found, rolled back."
            )

        if member.nickname == safe_new_nickname:
            return None

        try:
            await service.change_nickname(member.id, safe_new_nickname)
        except UniqueNicknameViolation:
            return await self._handle_nickname_conflict(
                context, service, before.display_name, safe_new_nickname
            )

        return (
            f":information: **Name changed:** {after.mention} "
            f"**{before.display_name}** → **{safe_new_nickname}**."
        )

    async def _handle_nickname_conflict(
        self,
        context: MemberUpdateContext,
        service: MemberService,
        previous_name: str,
        new_name: str,
    ) -> Optional[str]:
        conflicting_db_member = await service.get_member_by_nickname(new_name)

        if not conflicting_db_member:
            if not await self._rollback(context, previous_name):
                return None
            return (
                f":warning: **Name changed:** {context.after.mention} "
                f"**{previous_name}** → **{new_name}**. "
                f"Conflict, rolled back."
            )

        conflicting_discord_member = context.report_channel.guild.get_member(
            conflicting_db_member.discord_id
        )

        if not await self._rollback(context, previous_name):
            return None

        conflict_info = ""
        if conflicting_discord_member:
            conflict_info = f" with {conflicting_discord_member.mention}"

        return (
            f":warning: **Name changed:** {context.after.mention} "
            f"**{previous_name}** → **{new_name}**. "
            f"Conflict{conflict_info}, rolled back."
        )


member_update_emitter.register(NicknameChangeHandler())
