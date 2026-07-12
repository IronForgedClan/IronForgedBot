import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_perm
from api.deps import get_current_consumer, get_db_session
from api.permissions import PERM
from api.routers.members import _resolve_member
from api.schemas.common import ApiResponse, ResponseMeta
from api.schemas.ingot import (
    IngotBalance,
    IngotTransaction,
    IngotTransactionsResponse,
)
from ironforgedbot.models import Changelog
from ironforgedbot.services.changelog_service import ChangelogService
from ironforgedbot.services.service_factory import create_member_service

from api.models import ApiConsumer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/members", tags=["ingots"])


@router.get("/{member_id}/ingots", response_model=ApiResponse)
async def get_member_ingots(
    request: Request,
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
):
    request.state.required_perm = PERM.INGOTS_READ
    await require_perm(PERM.INGOTS_READ)(consumer=consumer)

    service = create_member_service(session)
    member = await _resolve_member(service, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No member with id={member_id}",
        )

    return ApiResponse(
        data=IngotBalance(
            discord_id=member.discord_id,
            nickname=member.nickname,
            ingots=member.ingots,
        ).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{member_id}/ingots/transactions", response_model=ApiResponse)
async def get_member_ingot_transactions(
    request: Request,
    member_id: str,
    days: int | None = Query(default=None, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
):
    request.state.required_perm = PERM.INGOTS_READ_TRANSACTIONS
    await require_perm(PERM.INGOTS_READ_TRANSACTIONS)(consumer=consumer)

    service = create_member_service(session)
    member = await _resolve_member(service, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No member with id={member_id}",
        )

    after: datetime | None = None
    if days is not None:
        after = datetime.now(tz=timezone.utc) - timedelta(days=days)

    changelog_service = ChangelogService(session)
    logs: list[Changelog] = await changelog_service.latest_ingot_transactions(
        discord_id=member.discord_id, quantity=limit, after=after
    )

    return ApiResponse(
        data=IngotTransactionsResponse(
            discord_id=member.discord_id,
            transactions=[IngotTransaction.from_changelog(log) for log in logs],
        ).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
