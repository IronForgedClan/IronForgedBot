import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_consumer, get_db_session
from api.models import ApiConsumer
from api.perm import requires_perm
from api.permissions import PERM
from api.rate_limit import rate_limit
from api.schemas.common import ApiResponse, ResponseMeta
from api.schemas.score import (
    PlayerScoreResponse,
    ScoreHistoryQueryParams,
    ScoreHistoryResponse,
)
from ironforgedcore.exceptions.score_exceptions import HiscoresNotFound
from ironforgedcore.http import HTTP
from ironforgedbot.services import (
    score_service as score_service_module,
)  # noqa: E402  -- bot-only service (uses cache + storage.data)
from ironforgedcore.services.service_factory import (
    create_member_service,
    create_score_history_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/players", tags=["scores"])


@router.get("/{rsn}/score", response_model=ApiResponse)
async def get_player_score(
    request: Request,
    rsn: str,
    bypass_cache: bool = Query(default=False),
    consumer: ApiConsumer = Depends(get_current_consumer),
    _perm: None = Depends(requires_perm(PERM.SCORES_READ)),
    _: None = Depends(rate_limit()),
):

    if not rsn or len(rsn) > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid player name",
        )

    score_service = score_service_module.get_score_service(HTTP)
    try:
        breakdown = await score_service.get_player_score(rsn, bypass_cache)
    except HiscoresNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player not found on hiscores: {rsn}",
        )

    return ApiResponse(
        data=PlayerScoreResponse.from_breakdown(rsn, breakdown).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{rsn}/score-history", response_model=ApiResponse)
async def get_player_score_history(
    request: Request,
    rsn: str,
    days: str = Query(default="7,30,90"),
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
    _perm: None = Depends(requires_perm(PERM.SCORES_READ_HISTORY)),
    _: None = Depends(rate_limit()),
):

    try:
        params = ScoreHistoryQueryParams.parse(days)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    member_service = create_member_service(session)
    member = await member_service.get_member_by_rsn_or_raise(rsn)

    score_service = create_score_history_service(session)
    score_history = await score_service.get_score_history(
        member.discord_id, params.periods
    )

    return ApiResponse(
        data=ScoreHistoryResponse.from_periods(
            member.discord_id, score_history
        ).model_dump(mode="json"),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
