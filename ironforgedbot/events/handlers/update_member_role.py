import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.roles import (
    ROLE,
    check_member_has_role,
    get_highest_privilage_role_from_member,
)
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class UpdateMemberRoleHandler(BaseMemberUpdateHandler):
    """Handler for when a role is added to a member.

    Syncs the role change from Discord to the database.
    Runs after add/remove handlers (priority 40).
    """

    priority = 40

    @property
    def name(self) -> str:
        return "UpdateMemberRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        role_values = set(ROLE.list())
        has_role_added = bool(role_values & context.roles_added)
        return has_role_added and check_member_has_role(context.after, ROLE.MEMBER)

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        discord_member = context.after
        logger.debug(f"Processing role change for {discord_member.display_name}")

        role = get_highest_privilage_role_from_member(discord_member)

        if not role:
            return (
                f":warning: Role changed for {discord_member.mention}, "
                "but role could not be determined."
            )

        member = await service.get_member_by_discord_id(discord_member.id)

        if not member:
            return (
                f":warning: Role changed for {discord_member.mention}, "
                f"but database member not found. Role: {role}."
            )

        if member.role != role:
            previous_role = member.role
            await service.change_role(member.id, ROLE(role), admin_id=None)
            return (
                f":information: {discord_member.mention}'s **role** changed: "
                f"**{previous_role}** → **{ROLE(role)}**."
            )

        return None


member_update_emitter.register(UpdateMemberRoleHandler())
