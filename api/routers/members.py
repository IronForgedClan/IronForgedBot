import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_perm
from api.deps import get_current_consumer, get_db_session
from api.permissions import PERM
from api.rate_limit import default_rate_limit
from api.schemas.common import ApiResponse, ResponseMeta
from api.schemas.member import MemberFilter, MemberSummary
from ironforgedbot.models import Member
from ironforgedbot.services.service_factory import create_member_service

from api.models import ApiConsumer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/members", tags=["members"])


async def _resolve_member(service, member_id: str) -> Member | None:
    if member_id.isdigit():
        return await service.get_member_by_discord_id(int(member_id))
    return await service.get_member_by_id(member_id)


def _apply_member_filters(
    stmt, filter_: MemberFilter | None, role: str | None, rank: str | None
):
    if filter_ == MemberFilter.BOOSTER:
        stmt = stmt.where(Member.is_booster.is_(True), Member.active.is_(True))
    elif filter_ == MemberFilter.PROSPECT:
        stmt = stmt.where(Member.is_prospect.is_(True), Member.active.is_(True))
    elif filter_ == MemberFilter.BLACKLISTED:
        stmt = stmt.where(Member.is_blacklisted.is_(True), Member.active.is_(True))
    elif filter_ == MemberFilter.BANNED:
        stmt = stmt.where(Member.is_banned.is_(True))
    else:
        stmt = stmt.where(Member.active.is_(True))

    if role:
        stmt = stmt.where(Member.role == role)
    if rank:
        stmt = stmt.where(Member.rank == rank)
    return stmt


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
    _: None = Depends(default_rate_limit),
):
    request.state.required_perm = PERM.MEMBERS_LIST
    await require_perm(PERM.MEMBERS_LIST)(consumer=consumer)

    base_stmt = select(Member)
    base_stmt = _apply_member_filters(base_stmt, filter, role, rank)

    count_result = await session.execute(
        select(func.count()).select_from(base_stmt.subquery())
    )
    total = int(count_result.scalar_one())

    page_stmt = base_stmt.offset(offset).limit(limit)
    result = await session.execute(page_stmt)
    members = result.scalars().all()

    summaries = [MemberSummary.from_member(m) for m in members]
    return ApiResponse(
        data={
            "members": [s.model_dump(mode="json") for s in summaries],
            "total": total,
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
    _: None = Depends(default_rate_limit),
):
    request.state.required_perm = PERM.MEMBERS_READ
    await require_perm(PERM.MEMBERS_READ)(consumer=consumer)

    service = create_member_service(session)
    member = await _resolve_member(service, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No member with id={member_id}",
        )

    return ApiResponse(
        data=MemberSummary.from_member(member).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
