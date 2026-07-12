import json
import logging
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from api.audit import write_audit_row
from api.config import API_CONFIG
from api.http_utils import (
    PATH_MAX_LENGTH,
    REQUEST_ID_HEADER,
    USER_AGENT_MAX_LENGTH,
    get_client_ip,
)
from api.schemas.common import ApiError, ApiErrorResponse, ResponseMeta

logger = logging.getLogger(__name__)

_STALE_AFTER_MINUTES = 5
_SWEEP_PROBABILITY = 0.01


@dataclass
class _Bucket:
    window_start: int
    count: int


_state: dict[str, _Bucket] = {}
_sweep_counter: int = 0


def _current_minute() -> int:
    return int(time.time()) // 60


def _seconds_until_next_minute() -> int:
    return 60 - (int(time.time()) % 60)


def _sweep_if_due(force: bool = False) -> None:
    global _sweep_counter
    _sweep_counter += 1
    if not force and _sweep_counter % 100 != 0:
        return
    current = _current_minute()
    stale_before = current - _STALE_AFTER_MINUTES
    for key in list(_state.keys()):
        if _state[key].window_start < stale_before:
            del _state[key]


class RateLimit:
    def __init__(self, per_minute: int | None = None):
        if per_minute is None:
            per_minute = API_CONFIG.API_RATE_LIMIT_PER_MINUTE
        self.per_minute = per_minute

    async def __call__(self, request: Request) -> None:
        if self.per_minute <= 0:
            return

        consumer = getattr(request.state, "consumer", None)
        if consumer is not None:
            key = f"c{consumer['id']}"
        else:
            ip = get_client_ip(request)
            key = f"ip:{ip}" if ip else "ip:unknown"

        endpoint = f"{request.method} {request.url.path}"
        full_key = f"{key}|{endpoint}"

        _sweep_if_due()
        current = _current_minute()
        bucket = _state.get(full_key)
        if bucket is None or bucket.window_start != current:
            _state[full_key] = _Bucket(window_start=current, count=1)
            return

        bucket.count += 1
        if bucket.count > self.per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(_seconds_until_next_minute())},
            )


class PreAuthRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, per_minute: int | None = None):
        super().__init__(app)
        if per_minute is None:
            per_minute = API_CONFIG.API_PRE_AUTH_RATE_LIMIT_PER_MINUTE
        self.per_minute = per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.per_minute > 0:
            ip = get_client_ip(request)
            key = f"ip:{ip}" if ip else "ip:unknown"
            full_key = f"preauth|{key}|{request.method} {request.url.path}"
            _sweep_if_due()
            current = _current_minute()
            bucket = _state.get(full_key)
            if bucket is None or bucket.window_start != current:
                _state[full_key] = _Bucket(window_start=current, count=1)
            else:
                bucket.count += 1
                if bucket.count > self.per_minute:
                    return await _build_blocked_response(request)
        return await call_next(request)


async def _build_blocked_response(request: Request) -> Response:
    request_id = str(uuid4())
    request.state.request_id = request_id

    client_ip = get_client_ip(request)
    user_agent = (request.headers.get("user-agent") or "")[:USER_AGENT_MAX_LENGTH]
    path = request.url.path[:PATH_MAX_LENGTH]

    await write_audit_row(
        method=request.method,
        path=path,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        duration_ms=0,
        client_ip=client_ip,
        user_agent=user_agent,
        request_id=request_id,
        consumer_id=None,
        consumer_name=None,
        consumer_perms=None,
        required_perm=None,
        error="Rate limit exceeded (pre-auth)",
    )

    body = ApiErrorResponse(
        error=ApiError(code="rate_limited", message="Rate limit exceeded"),
        meta=ResponseMeta(request_id=request_id),
    )
    return Response(
        content=json.dumps(body.model_dump(mode="json")),
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        media_type="application/json",
        headers={
            "Retry-After": str(_seconds_until_next_minute()),
            REQUEST_ID_HEADER: request_id,
        },
    )


default_rate_limit = RateLimit()
health_rate_limit = RateLimit(per_minute=2)
