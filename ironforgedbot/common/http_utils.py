"""HTTP utility functions for monitoring and health checking."""

import logging
from typing import Dict, Any
from ironforgedbot.http import HTTP

logger = logging.getLogger(__name__)


async def get_http_health_status() -> Dict[str, Any]:
    """Get comprehensive health status of the HTTP client."""
    try:
        is_healthy = await HTTP.health_check()

        status = {
            "healthy": is_healthy,
            "session_active": (
                HTTP.session is not None and not HTTP.session.closed
                if HTTP.session
                else False
            ),
            "connector_info": None,
        }

        if HTTP.session and hasattr(HTTP.session, "_connector"):
            connector = HTTP.session._connector
            status["connector_info"] = {
                "limit": getattr(connector, "_limit", "unknown"),
                "limit_per_host": getattr(connector, "_limit_per_host", "unknown"),
                "connections_count": len(getattr(connector, "_conns", {})),
            }

        return status

    except Exception as e:
        logger.error(f"Failed to get HTTP health status: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "session_active": False,
            "connector_info": None,
        }


async def force_http_cleanup():
    """Force cleanup of HTTP resources (use with caution)."""
    try:
        await HTTP.cleanup()
        logger.info("HTTP cleanup completed successfully")
        return True
    except Exception as e:
        logger.error(f"HTTP cleanup failed: {e}")
        return False
