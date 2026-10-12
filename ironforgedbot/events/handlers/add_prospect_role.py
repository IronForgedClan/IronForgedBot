import logging
import threading
import time
from collections.abc import Callable
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import find_emoji, get_discord_role
from ironforgedbot.common.welcome import send_welcome_messages_with_report
from ironforgedcore.common.roles import ROLE
from ironforgedcore.common.role_names import PROSPECT_ROLE_NAME
from ironforgedbot.common.roles_discord import check_member_has_role
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedcore.services.member_service import MemberService

logger = logging.getLogger(__name__)
PROSPECT_WELCOME_COOLDOWN_SECONDS = 10 * 60


class _InMemoryCooldown:
    def __init__(
        self, cooldown_seconds: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._expires_at: dict[int, float] = {}
        self._lock = threading.Lock()

    def claim(self, discord_id: int) -> bool:
        now = self._clock()
        with self._lock:
            self._expires_at = {
                user_id: expires_at
                for user_id, expires_at in self._expires_at.items()
                if expires_at > now
            }
            if discord_id in self._expires_at:
                return False

            self._expires_at[discord_id] = now + self._cooldown_seconds
            return True


_PROSPECT_WELCOME_COOLDOWN = _InMemoryCooldown(PROSPECT_WELCOME_COOLDOWN_SECONDS)


class AddProspectRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Prospect role is added to a member.

    Updates the is_prospect flag and cleans up Guest/Applicant roles.
    Also add Member role if not present.
    Runs at priority 20 after add/remove member handlers.
    """

    priority = 20

    @property
    def name(self) -> str:
        return "AddProspectRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return PROSPECT_ROLE_NAME in context.roles_added

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        prospect_emoji = find_emoji(PROSPECT_ROLE_NAME)

        member = context.after
        logger.debug(f"Processing Prospect role addition for {member.display_name}")

        role_changes = []

        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_prospect=True)
            logger.debug(f"Set is_prospect=True for {member.display_name}")

        if check_member_has_role(member, ROLE.APPLICANT):
            applicant_role = get_discord_role(
                context.report_channel.guild, ROLE.APPLICANT
            )
            if applicant_role is None:
                raise ValueError("Unable to access Applicant role values")

            await member.remove_roles(
                applicant_role, reason="Prospect: remove Applicant role"
            )

        if check_member_has_role(member, ROLE.GUEST):
            guest_role = get_discord_role(context.report_channel.guild, ROLE.GUEST)
            if guest_role is None:
                raise ValueError("Unable to access Guest role values")

            await member.remove_roles(guest_role, reason="Prospect: remove Guest role")

        if not check_member_has_role(member, ROLE.MEMBER):
            member_role = get_discord_role(context.report_channel.guild, ROLE.MEMBER)
            if member_role is None:
                raise ValueError("Unable to access Member role value")

            await member.add_roles(member_role, reason="Prospect: adding Member role")
            member_update_emitter.suppress_next_for(context.discord_id)

        report_content = f"{prospect_emoji} {member.mention} is now a **Prospect**."
        await context.report_channel.send(report_content)

        if not _PROSPECT_WELCOME_COOLDOWN.claim(member.id):
            logger.info(
                f"Skipping duplicate Prospect welcome for {member.display_name} "
                f"(ID: {member.id}) within cooldown"
            )
            return None

        try:
            await send_welcome_messages_with_report(member, context.report_channel)
        except Exception:
            logger.exception(
                f"Unable to send welcome messages to Prospect {member.display_name}"
            )

        return None


member_update_emitter.register(AddProspectRoleHandler())
