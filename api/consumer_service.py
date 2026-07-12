import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiConsumer, ApiPermission
from api.tokens import hash_token

try:
    from ironforgedbot.database.database import db
except RuntimeError:
    db = None


def generate_token() -> str:
    return f"iron_{secrets.token_urlsafe(32)}"


async def create_consumer(
    session: AsyncSession,
    name: str,
    perms: list[str] | None = None,
    description: str | None = None,
) -> tuple[ApiConsumer, str]:
    token = generate_token()
    consumer = ApiConsumer(
        name=name,
        token_hash=hash_token(token),
        perms=perms or [],
        enabled=True,
        created_at=datetime.now(tz=timezone.utc),
        description=description,
    )
    session.add(consumer)
    await session.commit()
    await session.refresh(consumer)
    return consumer, token


async def list_consumers(session: AsyncSession) -> list[ApiConsumer]:
    result = await session.execute(select(ApiConsumer).order_by(ApiConsumer.name))
    return list(result.scalars().all())


async def get_consumer_by_name(session: AsyncSession, name: str) -> ApiConsumer | None:
    result = await session.execute(select(ApiConsumer).where(ApiConsumer.name == name))
    return result.scalar_one_or_none()


async def grant_perm(session: AsyncSession, name: str, perm: str) -> ApiConsumer:
    consumer = await get_consumer_by_name(session, name)
    if consumer is None:
        raise ValueError(f"Consumer not found: {name}")

    perm_exists = await session.execute(
        select(ApiPermission).where(ApiPermission.name == perm)
    )
    if perm_exists.scalar_one_or_none() is None:
        raise ValueError(f"Permission not registered: {perm}")

    if perm not in consumer.perms:
        consumer.perms = [*consumer.perms, perm]
    await session.commit()
    await session.refresh(consumer)
    return consumer


async def revoke_perm(session: AsyncSession, name: str, perm: str) -> ApiConsumer:
    consumer = await get_consumer_by_name(session, name)
    if consumer is None:
        raise ValueError(f"Consumer not found: {name}")

    if perm in consumer.perms:
        consumer.perms = [p for p in consumer.perms if p != perm]
    await session.commit()
    await session.refresh(consumer)
    return consumer


async def set_perms(session: AsyncSession, name: str, perms: list[str]) -> ApiConsumer:
    consumer = await get_consumer_by_name(session, name)
    if consumer is None:
        raise ValueError(f"Consumer not found: {name}")

    existing = {
        row
        for row in (await session.execute(select(ApiPermission.name))).scalars().all()
    }
    unknown = [p for p in perms if p not in existing]
    if unknown:
        raise ValueError(f"Unknown permissions: {', '.join(unknown)}")

    consumer.perms = perms
    await session.commit()
    await session.refresh(consumer)
    return consumer


async def set_enabled(session: AsyncSession, name: str, enabled: bool) -> ApiConsumer:
    consumer = await get_consumer_by_name(session, name)
    if consumer is None:
        raise ValueError(f"Consumer not found: {name}")
    consumer.enabled = enabled
    await session.commit()
    await session.refresh(consumer)
    return consumer


async def rotate_token(session: AsyncSession, name: str) -> tuple[ApiConsumer, str]:
    consumer = await get_consumer_by_name(session, name)
    if consumer is None:
        raise ValueError(f"Consumer not found: {name}")
    token = generate_token()
    consumer.token_hash = hash_token(token)
    await session.commit()
    await session.refresh(consumer)
    return consumer, token


async def delete_consumer(session: AsyncSession, name: str) -> bool:
    consumer = await get_consumer_by_name(session, name)
    if consumer is None:
        return False
    await session.delete(consumer)
    await session.commit()
    return True
