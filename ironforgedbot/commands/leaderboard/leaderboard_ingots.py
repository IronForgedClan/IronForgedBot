from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    LeaderboardEntry,
)
from ironforgedbot.services.service_factory import create_member_service


async def fetch_ingots(session: AsyncSession) -> list[LeaderboardEntry]:
    member_service = create_member_service(session)
    members = await member_service.get_all_active_members(include_prospects=False)
    return [
        LeaderboardEntry(
            discord_id=m.discord_id,
            nickname=m.nickname,
            value=m.ingots,
        )
        for m in members
    ]


INGOTS_LEADERBOARD = LeaderboardConfig(
    title="Ingot Leaderboard",
    description="The clan rich list. A measure of loyalty, grind and contribution. See where you stand among Iron Forged's wealthiest members.",
    column_header="Ingots",
    emoji="Ingot",
    sort_key=lambda e: e.value,
    value_formatter=lambda e: f"{e.value:,}",
    fetcher=fetch_ingots,
)
