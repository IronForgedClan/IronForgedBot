import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import find_emoji, get_discord_role
from ironforgedbot.common.roles import ROLE, PROSPECT_ROLE_NAME, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


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
        member = context.after
        logger.debug(f"Processing Prospect role addition for {member.display_name}")

        report_content = (
            f"{find_emoji('Prospect')} {member.mention} has been "
            f"given the {text_bold(PROSPECT_ROLE_NAME)} role."
        )
        report_message = await context.report_channel.send(
            report_content + " Fixing roles..."
        )

        roles_removed = ""
        roles_added = ""

        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_prospect=True)
            logger.debug(f"Set is_prospect=True for {member.display_name}")

        # Remove Applicant role
        if check_member_has_role(member, ROLE.APPLICANT):
            applicant_role = get_discord_role(
                context.report_channel.guild, ROLE.APPLICANT
            )
            if applicant_role is None:
                raise ValueError("Unable to access Applicant role values")

            roles_removed += f" {text_bold(ROLE.APPLICANT)},"
            await member.remove_roles(
                applicant_role, reason="Prospect: remove Applicant role"
            )
            member_update_emitter.suppress_next_for(context.discord_id)

        # Remove Guest role
        if check_member_has_role(member, ROLE.GUEST):
            guest_role = get_discord_role(context.report_channel.guild, ROLE.GUEST)
            if guest_role is None:
                raise ValueError("Unable to access Guest role values")

            roles_removed += f" {text_bold(ROLE.GUEST)},"
            await member.remove_roles(guest_role, reason="Prospect: remove Guest role")
            member_update_emitter.suppress_next_for(context.discord_id)

        # Add Member role
        if not check_member_has_role(member, ROLE.MEMBER):
            member_role = get_discord_role(context.report_channel.guild, ROLE.MEMBER)
            if member_role is None:
                raise ValueError("Unable to access Member role value")

            roles_added += f" {text_bold(ROLE.MEMBER)},"
            await member.add_roles(member_role, reason="Prospect: adding Member role")
            member_update_emitter.suppress_next_for(context.discord_id)

        msg = ""
        if roles_added:
            msg = f" Added roles: {roles_added[:-1]}."
        if roles_removed:
            msg += f" Removed roles: {roles_removed[:-1]}."

        await report_message.edit(content=report_content + msg)
        return None  # Already sent/edited message


member_update_emitter.register(AddProspectRoleHandler())
