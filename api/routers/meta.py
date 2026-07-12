import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import API_CONFIG
from api.deps import get_db_session
from api.rate_limit import public_rate_limit
from api.schemas.common import ApiResponse, ResponseMeta

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=ApiResponse)
async def health(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(public_rate_limit(per_minute=2)),
) -> JSONResponse:
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check DB ping failed: %s", exc)
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "version": API_CONFIG.api_version,
        "environment": API_CONFIG.base.ENVIRONMENT.value,
    }
    code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    body = ApiResponse(
        data=payload, meta=ResponseMeta(request_id=request.state.request_id)
    )
    return JSONResponse(status_code=code, content=body.model_dump(mode="json"))
