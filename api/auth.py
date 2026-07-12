import hashlib

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiConsumer
from api.tokens import hash_token


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed Authorization header",
        )
    return parts[1].strip()


async def verify_bearer(
    authorization: str | None,
    session: AsyncSession,
) -> ApiConsumer:
    token = _extract_bearer(authorization)
    token_hash = hash_token(token)

    result = await session.execute(
        select(ApiConsumer).where(ApiConsumer.token_hash == token_hash)
    )
    consumer = result.scalar_one_or_none()

    if consumer is None or not consumer.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or disabled credentials",
        )

    return consumer
