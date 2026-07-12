import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_perm
from api.deps import get_current_consumer, get_db_session
from api.permissions import PERM
from api.schemas.common import ApiResponse, ResponseMeta
from api.schemas.score import PlayerScoreResponse, ScoreHistoryResponse
from ironforgedbot.exceptions.score_exceptions import HiscoresNotFound
from ironforgedbot.http import HTTP
from ironforgedbot.services import score_service as score_service_module
from ironforgedbot.services.service_factory import (
    create_member_service,
    create_score_history_service,
)

from api.models import ApiConsumer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/players", tags=["scores"])


@router.get("/{rsn}/score", response_model=ApiResponse)
async def get_player_score(
    request: Request,
    rsn: str,
    bypass_cache: bool = Query(default=False),
    consumer: ApiConsumer = Depends(get_current_consumer),
):
    request.state.required_perm = PERM.SCORES_READ
    await require_perm(PERM.SCORES_READ)(consumer=consumer)

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
        meta=ResponseMeta(),
    )


@router.get("/{rsn}/score-history", response_model=ApiResponse)
async def get_player_score_history(
    request: Request,
    rsn: str,
    days: str = Query(default="7,30,90"),
    session: AsyncSession = Depends(get_db_session),
    consumer: ApiConsumer = Depends(get_current_consumer),
):
    request.state.required_perm = PERM.SCORES_READ_HISTORY
    await require_perm(PERM.SCORES_READ_HISTORY)(consumer=consumer)

    try:
        periods = [int(d.strip()) for d in days.split(",") if d.strip()]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid days parameter; expected comma-separated integers",
        )

    if not periods or any(p < 1 or p > 365 for p in periods):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Each day value must be between 1 and 365",
        )

    member_service = create_member_service(session)
    member = await member_service.get_member_by_rsn(rsn)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No member with rsn={rsn}",
        )

    score_service = create_score_history_service(session)
    score_history = await score_service.get_score_history(member.discord_id, periods)

    return ApiResponse(
        data=ScoreHistoryResponse.from_periods(
            member.discord_id, score_history
        ).model_dump(mode="json"),
        meta=ResponseMeta(),
    )
