import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_consumer, get_db_session
from api.models import ApiConsumer
from api.perm import requires_perm
from api.permissions import PERM
from api.rate_limit import rate_limit
from api.schemas.common import ApiResponse, ResponseMeta
from api.schemas.member import MemberFilter, MemberSummary
from ironforgedbot.services.member_service import MemberListFilter
from ironforgedbot.services.service_factory import create_member_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=ApiResponse)
async def list_members(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    role: str | None = Query(default=None),
    rank: str | None = Query(default=None),
    filter: MemberFilter | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
    _perm: None = Depends(requires_perm(PERM.MEMBERS_LIST)),
    _: None = Depends(rate_limit()),
):

    service = create_member_service(session)
    filter_kind = MemberListFilter(filter.value) if filter else None
    result = await service.list_members(
        filter=filter_kind, role=role, rank=rank, limit=limit, offset=offset
    )

    return ApiResponse(
        data={
            "members": [
                MemberSummary.from_member(m).model_dump(mode="json")
                for m in result.members
            ],
            "total": result.total,
            "limit": limit,
            "offset": offset,
        },
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{member_id}", response_model=ApiResponse)
async def get_member(
    request: Request,
    member_id: str,
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
    _perm: None = Depends(requires_perm(PERM.MEMBERS_READ)),
    _: None = Depends(rate_limit()),
):

    service = create_member_service(session)
    member = await service.get_member_by_id_or_discord_or_raise(member_id)

    return ApiResponse(
        data=MemberSummary.from_member(member).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
