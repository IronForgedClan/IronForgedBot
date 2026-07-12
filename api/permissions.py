import enum
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiPermission


class PERM(enum.StrEnum):
    META_READ = "meta:read"
    MEMBERS_READ = "members:read"
    MEMBERS_LIST = "members:list"
    INGOTS_READ = "ingots:read"
    INGOTS_READ_TRANSACTIONS = "ingots:read:transactions"
    SCORES_READ = "scores:read"
    SCORES_READ_HISTORY = "scores:read:history"


KNOWN_PERMS: list[tuple[str, str]] = [
    (PERM.META_READ, "Access /health and /version"),
    (PERM.MEMBERS_READ, "Read a single member record"),
    (PERM.MEMBERS_LIST, "List member directory"),
    (PERM.INGOTS_READ, "Read member ingot balances"),
    (PERM.INGOTS_READ_TRANSACTIONS, "Read ingot transaction history"),
    (PERM.SCORES_READ, "Read player score breakdowns"),
    (PERM.SCORES_READ_HISTORY, "Read player score history"),
]


async def seed_known_permissions(session: AsyncSession) -> None:
    result = await session.execute(select(ApiPermission.name))
    existing = {row for row in result.scalars().all()}

    now = datetime.now(tz=timezone.utc)
    for name, description in KNOWN_PERMS:
        if name in existing:
            continue
        session.add(ApiPermission(name=name, description=description, created_at=now))

    await session.commit()
