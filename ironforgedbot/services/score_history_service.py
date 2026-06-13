import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.logging_utils import log_database_operation
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.models.member import Member
from ironforgedbot.models.score_history import ScoreHistory
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class ScoreHistoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_service = MemberService(db)

    async def close(self):
        await self.member_service.close()
        await self.db.close()

    @log_database_operation(logger)
    async def track_score(
        self,
        discord_id: int,
        score: int,
    ) -> None:
        member = await self.member_service.get_member_by_discord_id(discord_id)
        if not member:
            raise ReferenceError(f"Member with id {discord_id} not found")

        self.db.add(
            ScoreHistory(member_id=member.id, score=score, nickname=member.nickname)
        )

        await self.db.commit()

    @log_database_operation(logger)
    async def get_score_history(
        self,
        discord_id: int,
        periods_days: list[int],
        tolerance_days: int = 3,
    ) -> dict[int, int | None]:
        """Return the nearest historical score for each requested period.

        For each value n in periods_days, finds the score_history row closest
        to (now - n days), subject to:
          - The snapshot date must be within tolerance_days of the target date.
          - The snapshot date must not be before the member's joined_date.

        Args:
            discord_id: The Discord ID of the member.
            periods_days: List of day offsets to look up (e.g. [7, 14, 30]).
            tolerance_days: Maximum days away from target date a snapshot may be.

        Returns:
            dict mapping each period (int) to its snapshot score (int) or None
            if no qualifying snapshot was found.

        Raises:
            ReferenceError: If no member with the given discord_id exists.
        """
        member = await self.member_service.get_member_by_discord_id(discord_id)
        if not member:
            raise ReferenceError(f"Member with id {discord_id} not found")

        now = datetime.now(tz=timezone.utc)
        tolerance = timedelta(days=tolerance_days)
        result: dict[int, int | None] = {}

        for days in periods_days:
            target = now - timedelta(days=days)

            if target < member.joined_date:
                result[days] = None
                continue

            window_start = target - tolerance
            window_end = target + tolerance

            stmt = (
                select(ScoreHistory)
                .where(
                    ScoreHistory.member_id == member.id,
                    ScoreHistory.date >= window_start,
                    ScoreHistory.date <= window_end,
                )
                .order_by(
                    func.abs(
                        func.timestampdiff(
                            text("SECOND"),
                            ScoreHistory.date,
                            target,
                        )
                    )
                )
                .limit(1)
            )

            query_result = await self.db.execute(stmt)
            row = query_result.scalar_one_or_none()
            result[days] = row.score if row is not None else None

        return result

    @log_database_operation(logger)
    async def get_latest_score_snapshot(self) -> list[Tuple[int, str, int]]:
        """Return the latest score snapshot for each eligible member.

        Eligible members are those who:
          - Are marked active
          - Are not prospects
          - Have at least one score_history entry

        Args:
            None

        Returns:
            A list of (discord_id, nickname, score) tuples, one per eligible
            member, representing their most recent snapshot. Members with no
            snapshots are excluded. Order is unspecified; callers should sort.
        """
        latest_per_member = (
            select(
                ScoreHistory.member_id,
                func.max(ScoreHistory.date).label("latest_date"),
            )
            .group_by(ScoreHistory.member_id)
            .subquery()
        )

        stmt = (
            select(
                Member.discord_id,
                ScoreHistory.nickname,
                ScoreHistory.score,
            )
            .join(Member, ScoreHistory.member_id == Member.id)
            .join(
                latest_per_member,
                (ScoreHistory.member_id == latest_per_member.c.member_id)
                & (ScoreHistory.date == latest_per_member.c.latest_date),
            )
            .where(
                Member.active == True,
                Member.is_prospect == False,
            )
        )

        result = await self.db.execute(stmt)
        return [(row.discord_id, row.nickname, row.score) for row in result]

    @log_database_operation(logger)
    async def get_staff_score_snapshot(
        self,
    ) -> list[Tuple[int, str, int, RANK]]:
        """Return the latest score snapshot for each active staff member.

        Eligible members are those who:
          - Are marked active
          - Are not prospects
          - Have a role of Staff or higher
          - Have at least one score_history entry

        Args:
            None

        Returns:
            A list of (discord_id, nickname, score, rank) tuples, one per
            eligible member, representing their most recent snapshot. Members
            with no snapshots are excluded. Order is unspecified; callers
            should sort.
        """
        staff_roles = ROLE.STAFF.or_higher()

        latest_per_member = (
            select(
                ScoreHistory.member_id,
                func.max(ScoreHistory.date).label("latest_date"),
            )
            .group_by(ScoreHistory.member_id)
            .subquery()
        )

        stmt = (
            select(
                Member.discord_id,
                ScoreHistory.nickname,
                ScoreHistory.score,
                Member.rank,
            )
            .join(Member, ScoreHistory.member_id == Member.id)
            .join(
                latest_per_member,
                (ScoreHistory.member_id == latest_per_member.c.member_id)
                & (ScoreHistory.date == latest_per_member.c.latest_date),
            )
            .where(
                Member.active == True,
                Member.is_prospect == False,
                Member.role.in_(staff_roles),
            )
        )

        result = await self.db.execute(stmt)
        return [(row.discord_id, row.nickname, row.score, row.rank) for row in result]
