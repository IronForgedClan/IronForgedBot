from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.services.service_factory import (
    create_member_service,
    create_score_history_service,
)


@dataclass
class LeaderboardEntry:
    """A single row of data for any leaderboard type."""

    discord_id: int
    nickname: str
    value: int


@dataclass
class LeaderboardConfig:
    """Defines a single leaderboard type.

    Adding a new leaderboard type requires:
      1. Adding a new LeaderboardConfig entry to LEADERBOARD_TYPES.
      2. Adding a matching app_commands.Choice to cmd_leaderboard's @app_commands.choices.
    """

    title: str
    description: str
    column_header: str
    emoji: str | None
    sort_key: Callable[[LeaderboardEntry], int]
    value_formatter: Callable[[LeaderboardEntry], str]
    fetcher: Callable[[AsyncSession], Awaitable[list[LeaderboardEntry]]]


async def _fetch_ingots(session: AsyncSession) -> list[LeaderboardEntry]:
    member_service = create_member_service(session)
    members = await member_service.get_all_active_members()
    return [
        LeaderboardEntry(
            discord_id=m.discord_id,
            nickname=m.nickname,
            value=m.ingots,
        )
        for m in members
    ]


async def _fetch_scores(session: AsyncSession) -> list[LeaderboardEntry]:
    score_history_service = create_score_history_service(session)
    rows = await score_history_service.get_latest_score_snapshot()
    return [
        LeaderboardEntry(discord_id=discord_id, nickname=nickname, value=score)
        for discord_id, nickname, score in rows
    ]


LEADERBOARD_TYPES: dict[str, LeaderboardConfig] = {
    "ingots": LeaderboardConfig(
        title="Ingot Leaderboard",
        description="The clan treasury rankings - a measure of loyalty, grind, and contribution. See where you stand among Iron Forged's wealthiest members.",
        column_header="Ingots",
        emoji="Ingot",
        sort_key=lambda e: e.value,
        value_formatter=lambda e: f"{e.value:,}",
        fetcher=_fetch_ingots,
    ),
    "score": LeaderboardConfig(
        title=":trophy: Score Leaderboard",
        description="The definitive measure of in-game achievement within Iron Forged. A ranking of members by their overall OSRS progression, calculated from hiscores data and updated twice daily.",
        column_header="Score",
        emoji=None,
        sort_key=lambda e: e.value,
        value_formatter=lambda e: f"{e.value:,}",
        fetcher=_fetch_scores,
    ),
}
