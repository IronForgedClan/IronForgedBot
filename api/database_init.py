import logging

from ironforgedcore.database import db

logger = logging.getLogger(__name__)


async def initialize_database() -> None:
    logger.info("Initializing API database")
    async with db.get_session():
        pass
    logger.info("API database initialized")
