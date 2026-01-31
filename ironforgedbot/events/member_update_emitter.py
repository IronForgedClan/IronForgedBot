import asyncio
import logging
import time
from typing import TYPE_CHECKING, Dict, List, Set

from ironforgedbot.events.member_events import HandlerResult, MemberUpdateContext

if TYPE_CHECKING:
    from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler

logger = logging.getLogger(__name__)


class MemberUpdateEmitter:
    """Specialized event emitter for member update events.

    Manages handler registration, execution ordering, and suppression
    to prevent infinite loops when handlers modify Discord state.
    """

    def __init__(self):
        self._handlers: List["BaseMemberUpdateHandler"] = []
        self._lock = asyncio.Lock()
        self._suppressed_ids: Set[int] = set()
        self._sorted = False

    def register(self, handler: "BaseMemberUpdateHandler") -> None:
        """Register a handler with the emitter.

        Handlers are sorted by priority before emission (lower priority runs first).
        """
        self._handlers.append(handler)
        self._sorted = False
        logger.debug(
            f"Registered handler: {handler.name} (priority={handler.priority})"
        )

    def suppress_next_for(self, discord_id: int) -> None:
        """Suppress the next event for a specific Discord user.

        Use this when a handler modifies Discord state (e.g., adds/removes roles)
        to prevent the resulting on_member_update from triggering handlers again.
        """
        self._suppressed_ids.add(discord_id)
        logger.debug(f"Suppressing next event for discord_id={discord_id}")

    def _is_suppressed(self, discord_id: int) -> bool:
        """Check if events for this Discord ID are currently suppressed."""
        if discord_id in self._suppressed_ids:
            self._suppressed_ids.discard(discord_id)
            logger.debug(f"Event suppressed for discord_id={discord_id}")
            return True
        return False

    def _ensure_sorted(self) -> None:
        """Sort handlers by priority if needed."""
        if not self._sorted:
            self._handlers.sort(key=lambda h: h.priority)
            self._sorted = True

    async def emit(self, context: MemberUpdateContext) -> List[HandlerResult]:
        """Emit a member update event to all registered handlers.

        Handlers are executed serially in priority order (lowest first).
        Each handler's should_handle() method is checked before execution.

        Returns a list of HandlerResult for each handler that was executed.
        """
        if self._is_suppressed(context.discord_id):
            return []

        async with self._lock:
            self._ensure_sorted()
            results: List[HandlerResult] = []

            for handler in self._handlers:
                if not handler.should_handle(context):
                    continue

                start_time = time.perf_counter()
                try:
                    await handler.handle(context)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    results.append(
                        HandlerResult(
                            handler_name=handler.name,
                            success=True,
                            duration_ms=duration_ms,
                        )
                    )
                except Exception as e:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    logger.exception(f"Handler {handler.name} failed: {e}")
                    results.append(
                        HandlerResult(
                            handler_name=handler.name,
                            success=False,
                            duration_ms=duration_ms,
                            error=e,
                        )
                    )

            return results


# Global singleton instance
member_update_emitter = MemberUpdateEmitter()
