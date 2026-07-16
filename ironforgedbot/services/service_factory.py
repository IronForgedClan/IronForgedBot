"""Bot-side service factory: re-exports core factories and adds bot-specific.

Bot-only `absent_service` stays in ironforgedbot because it depends on
gspread Sheets.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedcore.http import AsyncHttpClient
from ironforgedcore.services.changelog_service import ChangelogService
from ironforgedcore.services.ingot_service import IngotService
from ironforgedcore.services.member_service import MemberService
from ironforgedcore.services.raffle_service import RaffleService
from ironforgedcore.services.score_history_service import ScoreHistoryService
from ironforgedcore.services.service_factory import (
    create_changelog_service,
    create_ingot_service,
    create_member_service,
    create_raffle_service,
    create_score_history_service,
    get_wom_service,
)
from ironforgedcore.services.score_service import ScoreService, get_score_service
from ironforgedcore.services.wom_service import WomService
from ironforgedbot.services.absent_service import AbsentMemberService

__all__ = [
    "ServiceFactory",
    "create_member_service",
    "create_ingot_service",
    "create_raffle_service",
    "create_score_history_service",
    "create_changelog_service",
    "create_absent_service",
    "get_score_service",
    "get_wom_service",
]


logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating service instances with proper dependency injection."""

    @staticmethod
    def get_score_service(
        http_client: Optional[AsyncHttpClient] = None,
    ) -> ScoreService:
        """Get ScoreService instance (singleton pattern for HTTP-based service)."""
        return get_score_service(http_client)

    @staticmethod
    def create_member_service(session: AsyncSession) -> MemberService:
        return MemberService(session)

    @staticmethod
    def create_ingot_service(session: AsyncSession) -> IngotService:
        return IngotService(session)

    @staticmethod
    def create_raffle_service(session: AsyncSession) -> RaffleService:
        return RaffleService(session)

    @staticmethod
    def create_score_history_service(session: AsyncSession) -> ScoreHistoryService:
        return ScoreHistoryService(session)

    @staticmethod
    def create_changelog_service(session: AsyncSession) -> ChangelogService:
        return ChangelogService(session)

    @staticmethod
    def create_absent_service(session: AsyncSession) -> AbsentMemberService:
        return AbsentMemberService(session)

    @staticmethod
    def get_wom_service() -> WomService:
        return get_wom_service()


def create_absent_service(session: AsyncSession) -> AbsentMemberService:
    """Create AbsentMemberService instance (bot-only — uses Google Sheets)."""
    return AbsentMemberService(session)
