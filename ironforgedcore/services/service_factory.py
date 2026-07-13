"""Core service factory: only services that have no bot-side dependencies."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedcore.http import AsyncHttpClient
from ironforgedcore.services.changelog_service import ChangelogService
from ironforgedcore.services.ingot_service import IngotService
from ironforgedcore.services.member_service import MemberService
from ironforgedcore.services.raffle_service import RaffleService
from ironforgedcore.services.score_history_service import ScoreHistoryService
from ironforgedcore.services.wom_service import WomService

logger = logging.getLogger(__name__)


def create_member_service(session: AsyncSession) -> MemberService:
    """Create MemberService instance."""
    return MemberService(session)


def create_ingot_service(session: AsyncSession) -> IngotService:
    """Create IngotService instance."""
    return IngotService(session)


def create_raffle_service(session: AsyncSession) -> RaffleService:
    """Create RaffleService instance."""
    return RaffleService(session)


def create_score_history_service(session: AsyncSession) -> ScoreHistoryService:
    """Create ScoreHistoryService instance."""
    return ScoreHistoryService(session)


def create_changelog_service(session: AsyncSession) -> ChangelogService:
    """Create ChangelogService instance."""
    return ChangelogService(session)


def get_wom_service() -> WomService:
    """Get WomService instance."""
    return WomService()
