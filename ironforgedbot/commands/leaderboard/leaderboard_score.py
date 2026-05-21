from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    LeaderboardEntry,
)
from ironforgedbot.services.service_factory import create_score_history_service


async def fetch_scores(session: AsyncSession) -> list[LeaderboardEntry]:
    score_history_service = create_score_history_service(session)
    rows = await score_history_service.get_latest_score_snapshot()
    return [
        LeaderboardEntry(discord_id=discord_id, nickname=nickname, value=score)
        for discord_id, nickname, score in rows
    ]


SCORE_LEADERBOARD = LeaderboardConfig(
    title=":trophy: Score Leaderboard",
    description="The definitive measure of in-game achievement. A ranking of members by their overall progression, calculated from hiscores data and updated twice a day.",
    column_header="Score",
    emoji=None,
    sort_key=lambda e: e.value,
    value_formatter=lambda e: f"{e.value:,}",
    fetcher=fetch_scores,
)
