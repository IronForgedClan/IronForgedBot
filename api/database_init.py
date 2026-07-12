import logging

from ironforgedbot.database.database import db
from sqlalchemy import select

from api.models import ApiPermission

from api.permissions import seed_known_permissions

logger = logging.getLogger(__name__)


async def initialize_database() -> None:
    logger.info("Initializing API database (seeding permissions)")

    async with db.get_session() as session:
        result = await session.execute(select(ApiPermission))
        existing = result.scalars().all()
        if existing:
            logger.info(
                f"Found {len(existing)} existing permissions; refreshing catalog"
            )

    async with db.get_session() as session:
        await seed_known_permissions(session)

    logger.info("API database initialized")
