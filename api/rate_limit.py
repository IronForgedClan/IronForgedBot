import time

from fastapi import Depends, HTTPException, Request, status

from api.config import API_CONFIG
from api.deps import get_current_consumer
from api.http_utils import get_client_ip
from api.models import ApiConsumer

_buckets: dict[str, tuple[int, int]] = {}
_BUCKET_TTL_MINUTES = 5


def current_window() -> int:
    return int(time.time()) // 60


def _check(bucket_key: str, per_minute: int) -> None:
    if per_minute <= 0:
        return
    now = int(time.time())
    window = now // 60
    stale = window - _BUCKET_TTL_MINUTES
    for k in list(_buckets):
        if _buckets[k][0] < stale:
            del _buckets[k]
    window_start, count = _buckets.get(bucket_key, (window, 0))
    if window_start != window:
        window_start, count = window, 0
    count += 1
    _buckets[bucket_key] = (window_start, count)
    if count > per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(60 - (now % 60))},
        )


def _bucket_key(request: Request, prefer_consumer: bool) -> str:
    if prefer_consumer:
        consumer = getattr(request.state, "consumer", None)
        if consumer is not None:
            return f"c{consumer['id']}|{request.method} {request.url.path}"
    ip = get_client_ip(request) or "unknown"
    return f"ip:{ip}|{request.method} {request.url.path}"


def rate_limit(*, per_minute: int | None = None):
    limit = per_minute if per_minute is not None else API_CONFIG.API_RATE_LIMIT

    async def dep(
        request: Request,
        _consumer: ApiConsumer = Depends(get_current_consumer),
    ) -> None:
        _check(_bucket_key(request, prefer_consumer=True), limit)

    return dep


def public_rate_limit(*, per_minute: int | None = None):
    limit = per_minute if per_minute is not None else API_CONFIG.API_RATE_LIMIT

    async def dep(request: Request) -> None:
        _check(_bucket_key(request, prefer_consumer=False), limit)

    return dep
