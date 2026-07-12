import logging

import uvicorn

from api.app import app
from api.config import API_CONFIG

logger = logging.getLogger(__name__)


def init_api() -> None:
    if not API_CONFIG.API_ENABLED:
        logger.info("API disabled (API_ENABLED=False); not starting")
        return

    logger.info(
        f"Starting IronForgedBot API v{API_CONFIG.api_version} on "
        f"{API_CONFIG.API_HOST}:{API_CONFIG.API_PORT}"
    )

    uvicorn.run(
        app,
        host=API_CONFIG.API_HOST,
        port=API_CONFIG.API_PORT,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    init_api()
