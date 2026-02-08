import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.roles import PROSPECT_ROLE_NAME
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class RemoveProspectRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Prospect role is removed from a member.

    Updates the is_prospect flag to False.
    Runs at priority 20 alongside other flag-modifying handlers.
    """

    priority = 20

    @property
    def name(self) -> str:
        return "RemoveProspectRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return PROSPECT_ROLE_NAME in context.roles_removed

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        member = context.after
        logger.debug(f"Processing Prospect role removal for {member.display_name}")

        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_prospect=False)
            logger.debug(f"Set is_prospect=False for {member.display_name}")

        return (
            f":outbox_tray: {member.mention} no longer has the "
            f"**{PROSPECT_ROLE_NAME}** role."
        )


member_update_emitter.register(RemoveProspectRoleHandler())
