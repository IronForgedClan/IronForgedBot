from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.database.database import db

from api.auth import verify_bearer
from api.models import ApiConsumer


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with db.get_session() as session:
        yield session


async def get_current_consumer(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ApiConsumer:
    auth_header = request.headers.get("Authorization")
    consumer = await verify_bearer(auth_header, session)
    request.state.consumer = {
        "id": consumer.id,
        "name": consumer.name,
        "perms": list(consumer.perms or []),
    }
    return consumer
