import logging
import time
from typing import Optional

from discord.errors import Forbidden
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import format_duration, get_discord_role
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import BLACKLISTED_ROLE_NAME, ROLE, BANNED_ROLE_NAME
from ironforgedbot.common.text_formatters import text_ul
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class AddBannedRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Banned (Slag) role is added to a member.

    Removes unmonitored roles and updates the is_banned flag.
    Runs at priority 20 alongside other flag-modifying handlers.
    """

    priority = 20

    @property
    def name(self) -> str:
        return "AddBannedRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return BANNED_ROLE_NAME in context.roles_added

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        start_time = time.perf_counter()
        member = context.after

        db_member = await service.get_member_by_discord_id(member.id)
        if db_member:
            await service.update_member_flags(db_member.id, is_banned=True)
            logger.debug(f"Set is_banned=True for {member.display_name}")

        # Get monitored roles that should be preserved
        monitored_roles = set(RANK.list() + ROLE.list() + GOD_ALIGNMENT.list())
        monitored_roles.add(BANNED_ROLE_NAME)
        monitored_roles.add(BLACKLISTED_ROLE_NAME)

        roles_to_remove = []
        for role in member.roles:
            if role.name == "@everyone":
                continue
            if role.name not in monitored_roles:
                roles_to_remove.append(role)

        if roles_to_remove:
            try:
                await member.remove_roles(
                    *roles_to_remove,
                    reason="Member banned. Removing unmonitored roles.",
                )
                member_update_emitter.suppress_next_for(context.discord_id)
            except Forbidden:
                logger.error(f"Forbidden from modifying {member.display_name}'s roles")
                return f":warning: The bot lacks permission to manage {member.mention}'s roles."
            except Exception as e:
                logger.error(
                    f"Exception when modifying {member.display_name}'s roles\n{roles_to_remove}"
                )
                return f":warning: Something went wrong trying to remove a role.\n{e}"

        # Remove the Member role to trigger the RemoveMemberRole handler
        member_role = get_discord_role(context.report_channel.guild, ROLE.MEMBER)
        if member_role and member_role in member.roles:
            await context.report_channel.send(
                f"Now removing {member.mention}'s **MEMBER** role..."
            )
            await member.remove_roles(member_role, reason="Member banned.")
            member_update_emitter.suppress_next_for(context.discord_id)

        end_time = time.perf_counter()

        roles_message = ""
        if roles_to_remove:
            roles_message = (
                "Removed the following unmonitored **discord roles** "
                f"from this user:\n{text_ul([r.name for r in roles_to_remove])}"
            )

        return (
            f":x: **Member banned:** {member.mention} has been __banned__. "
            f"{roles_message}"
            f"Processed in **{format_duration(start_time, end_time)}**."
        )


member_update_emitter.register(AddBannedRoleHandler())
