import asyncio
import logging
from typing import Awaitable, Callable

from discord.errors import HTTPException

from ironforgedbot.events import member_update_emitter

logger = logging.getLogger(__name__)

RETRYABLE_DISCORD_HTTP_STATUSES: frozenset[int] = frozenset({0, 429, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS: int = 3
DEFAULT_SUPPRESS_DURATION_MS: int = 5000


def _is_retryable_discord_http_error(exc: BaseException) -> bool:
    """Check whether the exception represents a transient Discord API failure."""
    if not isinstance(exc, HTTPException):
        return False
    status = getattr(exc, "status", 0)
    return status in RETRYABLE_DISCORD_HTTP_STATUSES


async def discord_write_with_retry(
    operation: str,
    discord_id: int,
    factory: Callable[[], Awaitable[None]],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    suppress_emitter: bool = True,
) -> None:
    """Run a discord member-mutation write with retry on transient HTTP errors."""
    sleep_time = 1
    for attempt in range(max_attempts):
        if suppress_emitter:
            member_update_emitter.suppress_next_for(
                discord_id, DEFAULT_SUPPRESS_DURATION_MS
            )
        try:
            await factory()
            return
        except Exception as e:
            if not _is_retryable_discord_http_error(e):
                raise
            if attempt == max_attempts - 1:
                logger.critical(e)
                raise
            logger.warning(
                f"Fail #{attempt + 1} for {operation} (HTTP {e.status}), "
                f"retrying after {sleep_time}s sleep..."
            )
            await asyncio.sleep(sleep_time)
            sleep_time *= 2
