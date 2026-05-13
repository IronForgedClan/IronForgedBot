import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.logging_utils import log_database_operation
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
