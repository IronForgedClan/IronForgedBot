import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class UpdateMemberRankHandler(BaseMemberUpdateHandler):
    """Handler for when a rank role is added to a member.

    Syncs the rank change from Discord to the database.
    Runs after add/remove handlers (priority 30).
    """

    priority = 30

    @property
    def name(self) -> str:
        return "UpdateMemberRank"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        rank_roles = set(RANK.list())
        has_rank_added = bool(rank_roles & context.roles_added)
        return has_rank_added and check_member_has_role(context.after, ROLE.MEMBER)

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        discord_member = context.after
        logger.debug(f"Processing rank change for {discord_member.display_name}")

        rank = get_rank_from_member(discord_member)

        if not rank:
            return (
                f"**Error:** Rank changed for {discord_member.mention}, "
                "but rank could not be determined."
            )

        if rank in GOD_ALIGNMENT.list():
            rank = RANK.GOD

        member = await service.get_member_by_discord_id(discord_member.id)

        if not member:
            return (
                f"**Error:** Rank role changed for {discord_member.mention}, "
                f"but database member not found. Rank: {rank}."
            )

        if member.rank != rank:
            await service.change_rank(member.id, RANK(rank))
            rank_emoji = find_emoji(rank)
            return (
                f"**ℹ️ Rank changed:** {discord_member.mention}'s rank was changed to "
                f"{rank_emoji} **{RANK(rank)}**. Database updated."
            )

        return None  # No change needed


member_update_emitter.register(UpdateMemberRankHandler())
