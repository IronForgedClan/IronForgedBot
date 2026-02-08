import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.roles import BLACKLISTED_ROLE_NAME
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class AddBlacklistedRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Blacklisted role is added to a member.

    Updates the is_blacklisted flag to True.
    Does NOT remove any roles - blacklisting is informational only.
    Runs at priority 20 alongside other flag-modifying handlers.
    """

    priority = 20

    @property
    def name(self) -> str:
        return "AddBlacklistedRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return BLACKLISTED_ROLE_NAME in context.roles_added

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        member = context.after
        logger.debug(f"Processing Blacklisted role addition for {member.display_name}")

        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_blacklisted=True)
            logger.debug(f"Set is_blacklisted=True for {member.display_name}")

        return f":information: **Blacklisted:** {member.mention} added."


member_update_emitter.register(AddBlacklistedRoleHandler())
