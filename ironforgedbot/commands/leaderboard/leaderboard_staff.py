from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    StaffLeaderboardEntry,
)
from ironforgedbot.services.service_factory import create_score_history_service


async def fetch_staff(session: AsyncSession) -> list[StaffLeaderboardEntry]:
    score_history_service = create_score_history_service(session)
    rows = await score_history_service.get_staff_score_snapshot()
    return [
        StaffLeaderboardEntry(
            discord_id=discord_id, nickname=nickname, value=score, rank=rank
        )
        for discord_id, nickname, score, rank in rows
    ]


STAFF_LEADERBOARD = LeaderboardConfig(
    title=":trophy: Staff Leaderboard",
    description="The staff who keep Iron Forged running, ranked by how much they actually play the game.",
    column_header="Score",
    emoji=None,
    sort_key=lambda e: e.value,
    value_formatter=lambda e: f"{e.value:,}",
    fetcher=fetch_staff,
)
