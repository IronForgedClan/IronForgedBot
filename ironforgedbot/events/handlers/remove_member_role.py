import logging
import time
from typing import Optional

from discord.errors import Forbidden
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import format_duration, get_discord_role
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_ul
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class RemoveMemberRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Member role is removed from a Discord user.

    Disables the member in the database and removes associated roles.
    Runs early (priority 10) since member record changes affect other handlers.
    """

    priority = 10

    @property
    def name(self) -> str:
        return "RemoveMemberRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return ROLE.MEMBER in context.roles_removed

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        start_time = time.perf_counter()
        member = context.after

        member_roles = set(role.name for role in member.roles)
        roles_to_remove = RANK.list() + ROLE.list() + GOD_ALIGNMENT.list()

        roles_removed = []
        for role_name in roles_to_remove:
            if role_name in member_roles:
                role = get_discord_role(context.report_channel.guild, role_name)
                if not role:
                    raise ValueError(f"Unable to get role {role_name}")
                roles_removed.append(role)

        if roles_removed:
            try:
                await member.remove_roles(
                    *roles_removed, reason="Member removed. Removing monitored roles."
                )
            except Forbidden:
                return f":warning: The bot lacks permission to manage {member.mention}'s roles."

        db_member = await service.get_member_by_discord_id(member.id)
        if not db_member:
            return (
                f":warning: Member {member.mention} has been removed, but "
                "cannot be found in the database."
            )

        await service.disable_member(db_member.id)

        end_time = time.perf_counter()

        roles_message = ""
        if roles_removed:
            roles_message = (
                f" Removed the following **discord roles** from this user:\n"
                f"{text_ul([r.name for r in roles_removed])}"
            )

        return (
            f":x: **Member disabled:** {member.mention} has been removed. "
            f"Disabled member in database.{roles_message}"
            f"Processed in **{format_duration(start_time, end_time)}**."
        )


member_update_emitter.register(RemoveMemberRoleHandler())
