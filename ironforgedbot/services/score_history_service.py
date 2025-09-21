import logging

from sqlalchemy.ext.asyncio import AsyncSession

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

    async def track_score(
        self,
        discord_id: int,
        score: int,
    ) -> None:
        member = await self.member_service.get_member_by_discord_id(discord_id)
        if not member:
            logger.error(
                f"Member with id {discord_id} not found when attempting to track score"
            )
            raise ReferenceError(f"Member with id {discord_id} not found")

        logger.debug(f"Recording score {score} for {member.nickname}")

        self.db.add(
            ScoreHistory(member_id=member.id, score=score, nickname=member.nickname)
        )

        await self.db.commit()
