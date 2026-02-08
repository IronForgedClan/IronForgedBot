import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.database.database import db
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class BaseMemberUpdateHandler(ABC):
    priority: int = 50  # Lower runs first

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the handler name for logging and results."""
        ...

    @abstractmethod
    def should_handle(self, context: MemberUpdateContext) -> bool:
        """Return True if this handler should process the given event.

        This is called before _execute() to determine if the handler
        should run.
        """
        ...

    @abstractmethod
    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        """Execute the handler logic.

        Args:
            context: The member update event context
            session: Active database session
            service: MemberService instance for database operations

        Returns:
            Optional message to send to the report channel.
            Return None for silent operations.
        """
        ...

    async def _on_error(
        self,
        context: MemberUpdateContext,
        error: Exception,
    ) -> Optional[str]:
        """Handle errors that occur during _execute().

        Override this method to implement rollback logic (e.g., removing
        a Discord role that was just added if the database operation fails).

        Args:
            context: The member update event context
            error: The exception that was raised

        Returns:
            Optional error message to send to the report channel.
        """
        logger.error(f"Handler {self.name} failed: {error}")
        return f":warning: **{self.name}** encountered an error: {error}"

    async def handle(self, context: MemberUpdateContext) -> None:
        """Execute the handler with timing, session management, and error handling.

        Do not override this method. Implement _execute() instead.
        """
        start_time = time.perf_counter()

        async with db.get_session() as session:
            service = MemberService(session)

            try:
                message = await self._execute(context, session, service)
                if message:
                    await context.report_channel.send(message)
            except Exception as e:
                error_message = await self._on_error(context, e)
                if error_message:
                    end_time = time.perf_counter()
                    duration_ms = (end_time - start_time) * 1000
                    await context.report_channel.send(
                        f"{error_message} ({duration_ms:.0f}ms)"
                    )
                raise
