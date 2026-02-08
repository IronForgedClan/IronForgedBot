import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.roles import BOOSTER_ROLE_NAME
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class AddBoosterRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Server Booster role is added to a member.

    Updates the is_booster flag to True.
    Runs at priority 20 alongside other flag-modifying handlers.
    """

    priority = 20

    @property
    def name(self) -> str:
        return "AddBoosterRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return BOOSTER_ROLE_NAME in context.roles_added

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        member = context.after
        logger.debug(f"Processing Server Booster role addition for {member.display_name}")

        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_booster=True)
            logger.debug(f"Set is_booster=True for {member.display_name}")

        return (
            f":star2: {member.mention} is now a "
            f"**{BOOSTER_ROLE_NAME}**! Thank you for the support!"
        )


member_update_emitter.register(AddBoosterRoleHandler())
