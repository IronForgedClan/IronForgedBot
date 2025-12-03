import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.logging_utils import log_database_operation
from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class ChangelogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_service = MemberService(db)

    async def close(self):
        await self.member_service.close()
        await self.db.close()

    @log_database_operation(logger)
    async def latest_ingot_transactions(
        self, discord_id: int, quantity: int
    ) -> list[Changelog]:
        if not isinstance(quantity, int):
            raise TypeError("Quantity must be a valid integer")

        if quantity < 1:
            return []

        result = await self.db.execute(
            select(Changelog)
            .join(Member, Changelog.member_id == Member.id)
            .where(Member.discord_id == discord_id)
            .where(
                (Changelog.change_type == ChangeType.ADD_INGOTS)
                | (Changelog.change_type == ChangeType.REMOVE_INGOTS)
            )
            .order_by(Changelog.timestamp.desc())
            .limit(quantity)
        )

        return list(result.scalars().all())
