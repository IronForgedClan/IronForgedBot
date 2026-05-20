from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession


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
      1. Create a new module (e.g. leaderboard_<name>.py) with a fetcher function
         and a named LeaderboardConfig constant.
      2. Register the constant in leaderboard_registry.LEADERBOARD_TYPES.
      3. Add a matching app_commands.Choice to cmd_leaderboard's @app_commands.choices.
    """

    title: str
    description: str
    column_header: str
    emoji: str | None
    sort_key: Callable[[LeaderboardEntry], int]
    value_formatter: Callable[[LeaderboardEntry], str]
    fetcher: Callable[[AsyncSession], Awaitable[list[LeaderboardEntry]]]
