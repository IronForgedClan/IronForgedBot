import asyncio
import logging
import time
from typing import TYPE_CHECKING, Dict, List

from ironforgedbot.events.member_events import HandlerResult, MemberUpdateContext

if TYPE_CHECKING:
    from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler

logger = logging.getLogger(__name__)

DEFAULT_SUPPRESSION_DURATION_MS = 2000


class MemberUpdateEmitter:
    def __init__(self):
        self._handlers: List["BaseMemberUpdateHandler"] = []
        self._lock = asyncio.Lock()
        self._suppressions: Dict[int, float] = {}  # discord_id -> expiry time
        self._sorted = False

    def register(self, handler: "BaseMemberUpdateHandler") -> None:
        self._handlers.append(handler)
        self._sorted = False
        logger.debug(
            f"Registered handler: {handler.name} (priority={handler.priority})"
        )

    def suppress_next_for(
        self, discord_id: int, duration_ms: int = DEFAULT_SUPPRESSION_DURATION_MS
    ) -> None:
        """Suppress the next event for a specific Discord user.

        Use this when a handler modifies Discord state (e.g., adds/removes roles)
        to prevent the resulting on_member_update from triggering handlers again.

        Args:
            discord_id: The Discord user ID to suppress events for.
            duration_ms: How long the suppression lasts (default 2000ms).
        """
        self._suppressions[discord_id] = time.time() + duration_ms / 1000
        logger.debug(
            f"Suppressing next event for discord_id={discord_id} "
            f"(expires in {duration_ms}ms)"
        )

    def _is_suppressed(self, discord_id: int) -> bool:
        """Check if events for this Discord ID are currently suppressed."""
        if discord_id not in self._suppressions:
            return False
        if time.time() < self._suppressions[discord_id]:
            del self._suppressions[discord_id]  # Consume the suppression
            logger.debug(f"Event suppressed for discord_id={discord_id}")
            return True
        del self._suppressions[discord_id]  # Expired, clean up
        return False

    def _ensure_sorted(self) -> None:
        if not self._sorted:
            self._handlers.sort(key=lambda h: h.priority)
            self._sorted = True

    async def emit(self, context: MemberUpdateContext) -> List[HandlerResult]:
        async with self._lock:
            if self._is_suppressed(context.discord_id):
                return []
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


member_update_emitter = MemberUpdateEmitter()
