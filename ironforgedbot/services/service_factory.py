"""Service factory for consistent service instantiation patterns."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.http import AsyncHttpClient
from ironforgedbot.services.absent_service import AbsentMemberService
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.services.raffle_service import RaffleService
from ironforgedbot.services.score_history_service import ScoreHistoryService
from ironforgedbot.services.score_service import get_score_service, ScoreService
from ironforgedbot.services.wom_service import WomClient

logger = logging.getLogger(__name__)

# Global service instances for stateless/long-lived services
_score_service_instance: Optional[ScoreService] = None


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
        """Create MemberService instance (per-session for database operations)."""
        return MemberService(session)

    @staticmethod
    def create_ingot_service(session: AsyncSession) -> IngotService:
        """Create IngotService instance with proper dependency injection."""
        return IngotService(session)

    @staticmethod
    def create_raffle_service(session: AsyncSession) -> RaffleService:
        """Create RaffleService instance with full dependency chain."""
        return RaffleService(session)

    @staticmethod
    def create_score_history_service(session: AsyncSession) -> ScoreHistoryService:
        """Create ScoreHistoryService instance."""
        return ScoreHistoryService(session)

    @staticmethod
    def create_absent_service(session: AsyncSession) -> AbsentMemberService:
        """Create AbsentMemberService instance."""
        return AbsentMemberService(session)

    @staticmethod
    async def get_wom_client() -> WomClient:
        """Get WomClient instance with application configuration."""
        from ironforgedbot.services.wom_service import get_wom_client
        return await get_wom_client()


# Convenience functions for cleaner imports
def create_member_service(session: AsyncSession) -> MemberService:
    """Create MemberService instance."""
    return ServiceFactory.create_member_service(session)


def create_ingot_service(session: AsyncSession) -> IngotService:
    """Create IngotService instance."""
    return ServiceFactory.create_ingot_service(session)


def create_raffle_service(session: AsyncSession) -> RaffleService:
    """Create RaffleService instance."""
    return ServiceFactory.create_raffle_service(session)


def create_score_history_service(session: AsyncSession) -> ScoreHistoryService:
    """Create ScoreHistoryService instance."""
    return ServiceFactory.create_score_history_service(session)


def create_absent_service(session: AsyncSession) -> AbsentMemberService:
    """Create AbsentMemberService instance."""
    return ServiceFactory.create_absent_service(session)


async def get_wom_client() -> WomClient:
    """Get WomClient instance."""
    # Delegate directly to avoid potential circular imports
    from ironforgedbot.services.wom_service import get_wom_client as get_client
    return await get_client()
