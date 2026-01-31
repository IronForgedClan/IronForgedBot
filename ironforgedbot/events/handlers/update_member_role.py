import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.roles import (
    ROLE,
    check_member_has_role,
    get_highest_privilage_role_from_member,
    has_booster_role,
    has_prospect_role,
    has_blacklisted_role,
    is_member_banned_by_role,
)
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class UpdateMemberRoleHandler(BaseMemberUpdateHandler):
    """Handler for syncing role and member flags on any role change.

    Updates:
    - Member's role field (based on highest privilege role)
    - Member flags: is_booster, is_prospect, is_blacklisted, is_banned

    Runs after rank updates (priority 40).
    """

    priority = 40

    @property
    def name(self) -> str:
        return "UpdateMemberRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return context.roles_changed and check_member_has_role(
            context.after, ROLE.MEMBER
        )

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        discord_member = context.after
        logger.debug(f"Processing role change for {discord_member.display_name}")

        member = await service.get_member_by_discord_id(discord_member.id)
        if not member:
            return None

        changes = []

        role = get_highest_privilage_role_from_member(discord_member)
        if role and member.role != role:
            previous_role = member.role
            await service.change_role(member.id, ROLE(role), admin_id=None)
            changes.append(f"**Role:** {previous_role} → {role}")
            logger.debug(
                f"Updated role for {discord_member.display_name}: {previous_role} -> {role}"
            )

        is_booster = has_booster_role(discord_member)
        is_prospect = has_prospect_role(discord_member)
        is_blacklisted = has_blacklisted_role(discord_member)
        is_banned = is_member_banned_by_role(discord_member)

        flag_changes = []
        if member.is_booster != is_booster:
            flag_changes.append(f"Booster: {member.is_booster} → {is_booster}")
        if member.is_prospect != is_prospect:
            flag_changes.append(f"Prospect: {member.is_prospect} → {is_prospect}")
        if member.is_blacklisted != is_blacklisted:
            flag_changes.append(
                f"Blacklisted: {member.is_blacklisted} → {is_blacklisted}"
            )
        if member.is_banned != is_banned:
            flag_changes.append(f"Banned: {member.is_banned} → {is_banned}")

        if flag_changes:
            await service.update_member_flags(
                member.id,
                is_booster=is_booster,
                is_prospect=is_prospect,
                is_blacklisted=is_blacklisted,
                is_banned=is_banned,
            )
            changes.append("**Flags:** " + ", ".join(flag_changes))
            logger.debug(
                f"Updated flags for {discord_member.display_name}: "
                f"booster={is_booster}, prospect={is_prospect}, "
                f"blacklisted={is_blacklisted}, banned={is_banned}"
            )

        if changes:
            return (
                f":information: **Member updated:** {discord_member.mention}\n"
                + "\n".join(f"- {change}" for change in changes)
            )

        return None


member_update_emitter.register(UpdateMemberRoleHandler())
