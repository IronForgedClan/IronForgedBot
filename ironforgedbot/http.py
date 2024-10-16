import logging
import sys
import aiohttp

from ironforgedbot.event_emitter import event_emitter

logger = logging.getLogger(__name__)


class AsyncHttpClient:
    def __init__(self):
        self.session = None

        event_emitter.on("shutdown", self.cleanup, priority=20)

    async def _initialize_session(self):
        """Initialize the aiohttp session."""
        if self.session is None or self.session.closed:
            logger.info("Initializing new session...")
            self.session = aiohttp.ClientSession()

    async def get(self, url, method="GET", params=None, headers=None, json_data=None):
        """Make a request to the provided URL with the given parameters."""
        await self._initialize_session()

        if not self.session:
            logger.critical("No session initialized")
            return

        try:
            async with self.session.request(
                method, url, params=params, headers=headers, json=json_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"Request failed with status: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            return None

    async def cleanup(self):
        if self.session:
            logger.info("Closing http session...")
            await self.session.close()


try:
    HTTP = AsyncHttpClient()
except Exception as e:
    logger.critical(e)
    sys.exit(1)
