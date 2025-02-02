import logging
import sys
from typing import Any, TypedDict

import aiohttp

from ironforgedbot.decorators import retry_on_exception
from ironforgedbot.event_emitter import event_emitter

logger = logging.getLogger(__name__)


class HttpResponse(TypedDict):
    status: int
    body: Any


class HttpException(Exception):
    def __init__(
        self,
        message="Unexpected response from target.",
    ):
        self.message = message
        super().__init__(self.message)


class AsyncHttpClient:
    def __init__(self):
        self.session = None

        event_emitter.on("shutdown", self.cleanup, priority=20)

    async def _initialize_session(self):
        """Initialize the aiohttp session."""
        if not self.session or self.session.closed:
            logger.info("Initializing new session...")
            self.session = aiohttp.ClientSession()

    @retry_on_exception(retries=5)
    async def get(self, url, params=None, headers=None, json_data=None) -> HttpResponse:
        """Make a request to the provided URL with the given parameters."""
        await self._initialize_session()
        assert self.session

        async with self.session.get(
            url, params=params, headers=headers, json=json_data
        ) as response:
            if response.status >= 500:
                logger.error(await response.text())
                raise HttpException(f"A remote server error occured: {response.status}")

            if response.status == 408:
                logger.error(await response.text())
                raise HttpException(
                    f"No response from remote server: {response.status}"
                )

            if response.status == 429:
                logger.error(await response.text())
                raise HttpException(
                    f"Rate limited or timed out response: {response.status}"
                )

            content_type = response.content_type.lower()

            if "json" in content_type:
                data = await response.json()
            elif "text" in content_type or "html" in content_type:
                data = await response.text()
            else:
                data = await response.read()

            return HttpResponse(status=response.status, body=data)

    async def cleanup(self):
        if self.session:
            logger.info("Closing http session...")
            await self.session.close()


try:
    HTTP = AsyncHttpClient()
except Exception as e:
    logger.critical(e)
    sys.exit(1)
