import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.http_utils import (
    ERROR_MAX_LENGTH,
    IP_MAX_LENGTH,
    PATH_MAX_LENGTH,
    REQUEST_ID_HEADER,
    USER_AGENT_MAX_LENGTH,
    get_client_ip,
)
from api.models import ApiAudit
from ironforgedcore.database import db

logger = logging.getLogger(__name__)


async def write_audit_row(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    client_ip: str | None,
    user_agent: str | None,
    request_id: str,
    consumer_id: int | None,
    consumer_name: str | None,
    consumer_perms: list[str] | None,
    required_perm: str | None,
    error: str | None,
) -> None:
    try:
        async with db.get_session() as session:
            session.add(
                ApiAudit(
                    timestamp=datetime.now(tz=timezone.utc),
                    request_id=request_id,
                    consumer_id=consumer_id,
                    consumer_name=consumer_name,
                    consumer_perms=consumer_perms,
                    required_perm=required_perm,
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    client_ip=client_ip[:IP_MAX_LENGTH] if client_ip else None,
                    user_agent=user_agent,
                    error=error,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to write api audit row")


class ApiAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        error_message: str | None = None
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception as exc:
            error_message = str(exc)[:ERROR_MAX_LENGTH]
            logger.exception("Request failed in audit middleware")
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            path = request.url.path[:PATH_MAX_LENGTH]
            method = request.method
            client_ip = get_client_ip(request)
            user_agent = (request.headers.get("user-agent") or "")[
                :USER_AGENT_MAX_LENGTH
            ]
            consumer = getattr(request.state, "consumer", None)
            required_perm = getattr(request.state, "required_perm", None)

            consumer_id = consumer["id"] if consumer is not None else None
            consumer_name = consumer["name"] if consumer is not None else None
            consumer_perms = list(consumer["perms"]) if consumer is not None else None

            await write_audit_row(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=user_agent,
                request_id=request_id,
                consumer_id=consumer_id,
                consumer_name=consumer_name,
                consumer_perms=consumer_perms,
                required_perm=required_perm,
                error=error_message,
            )
