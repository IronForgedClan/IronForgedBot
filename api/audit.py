import logging
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.models import ApiAudit
from ironforgedbot.database.database import db

logger = logging.getLogger(__name__)

_PATH_MAX_LENGTH = 512
_ERROR_MAX_LENGTH = 512
_USER_AGENT_MAX_LENGTH = 512
_IP_MAX_LENGTH = 64


class ApiAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        error_message: str | None = None
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_message = str(exc)[:_ERROR_MAX_LENGTH]
            logger.exception("Request failed in audit middleware")
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            path = request.url.path[:_PATH_MAX_LENGTH]
            method = request.method
            client_ip = _extract_client_ip(request)
            user_agent = (request.headers.get("user-agent") or "")[
                :_USER_AGENT_MAX_LENGTH
            ]
            consumer = getattr(request.state, "consumer", None)
            required_perm = getattr(request.state, "required_perm", None)

            consumer_id = consumer.id if consumer is not None else None
            consumer_name = consumer.name if consumer is not None else None
            consumer_perms = list(consumer.perms) if consumer is not None else None

            await self._write_audit(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                user_agent=user_agent,
                consumer_id=consumer_id,
                consumer_name=consumer_name,
                consumer_perms=consumer_perms,
                required_perm=required_perm,
                error=error_message,
            )

    async def _write_audit(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        client_ip: str | None,
        user_agent: str | None,
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
                        consumer_id=consumer_id,
                        consumer_name=consumer_name,
                        consumer_perms=consumer_perms,
                        required_perm=required_perm,
                        method=method,
                        path=path,
                        status_code=status_code,
                        duration_ms=duration_ms,
                        client_ip=client_ip[:_IP_MAX_LENGTH] if client_ip else None,
                        user_agent=user_agent,
                        error=error,
                    )
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to write api audit row")


def _extract_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return None
