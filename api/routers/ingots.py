import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_consumer, get_db_session
from api.models import ApiConsumer
from api.perm import requires_perm
from api.permissions import PERM
from api.rate_limit import rate_limit
from api.schemas.common import ApiResponse, ResponseMeta
from api.schemas.ingot import (
    IngotBalance,
    IngotTransaction,
    IngotTransactionsResponse,
)
from ironforgedcore.models import Changelog
from ironforgedcore.services.changelog_service import ChangelogService
from ironforgedcore.services.service_factory import create_member_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/members", tags=["ingots"])


@router.get("/{member_id}/ingots", response_model=ApiResponse)
async def get_member_ingots(
    request: Request,
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
    _perm: None = Depends(requires_perm(PERM.INGOTS_READ)),
    _: None = Depends(rate_limit()),
):

    service = create_member_service(session)
    member = await service.get_member_by_id_or_discord_or_raise(member_id)

    return ApiResponse(
        data=IngotBalance(
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
    _perm: None = Depends(requires_perm(PERM.INGOTS_READ_TRANSACTIONS)),
    _: None = Depends(rate_limit()),
):

    member_service = create_member_service(session)
    member = await member_service.get_member_by_id_or_discord_or_raise(member_id)

    changelog_service = ChangelogService(session)
    logs: list[Changelog] = await changelog_service.latest_ingot_transactions(
        discord_id=member.discord_id, quantity=limit, days=days
    )

    return ApiResponse(
        data=IngotTransactionsResponse(
            transactions=[
                IngotTransaction.from_changelog(log, getattr(log, "admin_member", None))
                for log in logs
            ],
        ).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
