import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ironforgedbot.common.logging_utils import log_database_operation
from ironforgedcore.models.changelog import Changelog, ChangeType
from ironforgedcore.models.member import Member
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
        self,
        discord_id: int,
        quantity: int,
        after: datetime | None = None,
        days: int | None = None,
    ) -> list[Changelog]:
        """Return the most recent ingot transactions for a member.

        Filters by timestamp when `after` is set, or when `days` is a positive
        int (in which case the cutoff is computed as `now - days`). `after`
        takes precedence when both are provided; `days <= 0` is treated as no
        filter (ignored).
        """
        if not isinstance(quantity, int):
            raise TypeError("Quantity must be a valid integer")

        if quantity < 1:
            return []

        AdminMember = aliased(Member, name="admin")

        if after is None and days is not None and days > 0:
            after = datetime.now(tz=timezone.utc) - timedelta(days=days)

        query = (
            select(Changelog)
            .join(Member, Changelog.member_id == Member.id)
            .outerjoin(AdminMember, Changelog.admin_id == AdminMember.id)
            .where(Member.discord_id == discord_id)
            .where(
                (Changelog.change_type == ChangeType.ADD_INGOTS)
                | (Changelog.change_type == ChangeType.REMOVE_INGOTS)
            )
        )

        if after is not None:
            query = query.where(Changelog.timestamp >= after)

        result = await self.db.execute(
            query.order_by(Changelog.timestamp.desc()).limit(quantity)
        )
        logs = list(result.scalars().all())

        admin_ids = {log.admin_id for log in logs if log.admin_id is not None}
        admin_map: dict[str, Member] = {}
        if admin_ids:
            admin_result = await self.db.execute(
                select(Member).where(Member.id.in_(admin_ids))
            )
            admin_map = {m.id: m for m in admin_result.scalars().all()}

        for log in logs:
            log.admin_member = admin_map.get(log.admin_id) if log.admin_id else None

        return logs
