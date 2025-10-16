import logging
import sys
import time
from typing import Any, TypedDict
import asyncio
from urllib.parse import urlparse

import aiohttp


from ironforgedbot.decorators.decorators import retry_on_exception
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
        self._session_lock = asyncio.Lock()
        self._last_request_time = {}
        self._min_request_delay = 1.0

        # Hosts that require session reset after each request to avoid blocking
        self._session_reset_hosts = {
            "secure.runescape.com",
            "hiscores.runescape.com",
            "services.runescape.com",
        }

        event_emitter.on("shutdown", self.cleanup, priority=20)

    async def _initialize_session(self):
        """Initialize the aiohttp session."""
        async with self._session_lock:
            if not self.session or self.session.closed:
                logger.debug("Initializing new session...")
                self.session = aiohttp.ClientSession()

    async def _rate_limit_check(self, url: str):
        """Ensure minimum delay between requests to the same host."""
        parsed_url = urlparse(url)
        host = parsed_url.netloc

        current_time = time.time()
        last_request = self._last_request_time.get(host, 0)
        time_since_last = current_time - last_request

        if time_since_last < self._min_request_delay:
            delay = self._min_request_delay - time_since_last
            logger.debug(
                f"Rate limiting: waiting {delay:.2f}s before request to {host}"
            )
            await asyncio.sleep(delay)

        self._last_request_time[host] = time.time()

    def _should_reset_session(self, url: str) -> bool:
        """Check if the URL requires session reset to avoid blocking.

        Args:
            url: The target URL to check

        Returns:
            True if session should be reset after the request, False otherwise
        """
        parsed_url = urlparse(url)
        return parsed_url.netloc in self._session_reset_hosts

    @retry_on_exception(retries=5)
    async def get(self, url, params=None, headers=None, json_data=None) -> HttpResponse:
        """Make a request to the provided URL with the given parameters."""
        try:
            await self._initialize_session()
            assert self.session

            await self._rate_limit_check(url)

            async with self.session.get(
                url, params=params, headers=headers, json=json_data
            ) as response:
                if response.status >= 500:
                    logger.debug(await response.text())
                    logger.warning(f"HTTP error code: {response.status}")
                    raise HttpException(
                        f"A remote server error occurred: {response.status}"
                    )

                if response.status == 408:
                    logger.debug(await response.text())
                    logger.warning(f"HTTP error code: {response.status}")
                    raise HttpException(
                        f"No response from remote server: {response.status}"
                    )

                if response.status == 429:
                    logger.debug(await response.text())
                    logger.warning(f"HTTP error code: {response.status}")
                    raise HttpException(
                        f"Rate limited or timed out response: {response.status}"
                    )

                content_type = response.content_type.lower()

                try:
                    if "json" in content_type:
                        data = await response.json()
                    elif "text" in content_type or "html" in content_type:
                        data = await response.text()
                    else:
                        data = await response.read()
                except Exception as e:
                    logger.error(f"Error reading GET response body from {url}: {e}")
                    raise HttpException(f"Failed to read response data: {e}")

            if self._should_reset_session(url):
                await self.cleanup()
                logger.debug(
                    f"Session reset for {urlparse(url).netloc} to prevent blocking"
                )

            return HttpResponse(status=response.status, body=data)

        except aiohttp.ServerTimeoutError:
            raise
        except aiohttp.ClientError as e:
            logger.error(f"GET client error for {url}: {e}")
            raise HttpException(f"GET request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected GET error for {url}: {e}", exc_info=True)
            raise HttpException(f"Unexpected GET error: {e}")

    async def post(
        self, url, data=None, json_data=None, params=None, headers=None
    ) -> HttpResponse:
        """Make a POST request to the provided URL."""
        try:
            await self._initialize_session()
            assert self.session

            async with self.session.post(
                url, data=data, json=json_data, params=params, headers=headers
            ) as response:
                content_type = response.content_type.lower()

                try:
                    if "json" in content_type:
                        body = await response.json()
                    elif "text" in content_type or "html" in content_type:
                        body = await response.text()
                    else:
                        body = await response.read()
                except Exception as e:
                    logger.error(f"Error reading POST response body from {url}: {e}")
                    raise HttpException(f"Failed to read response data: {e}")

                return HttpResponse(status=response.status, body=body)

        except aiohttp.ClientError as e:
            logger.error(f"POST client error for {url}: {e}")
            raise HttpException(f"POST request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected POST error for {url}: {e}", exc_info=True)
            raise HttpException(f"Unexpected POST error: {e}")

    async def health_check(self) -> bool:
        """Check if the HTTP client is healthy and responsive."""
        try:
            if not self.session or self.session.closed:
                await self._initialize_session()
            return self.session is not None and not self.session.closed
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def cleanup(self):
        """Cleanup the HTTP session."""
        if self.session:
            logger.debug("Closing http session...")
            await self.session.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._initialize_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    def __del__(self):
        """Destructor to ensure cleanup if not done explicitly."""
        if self.session and not self.session.closed:
            logger.warning("HTTP session not properly closed, forcing cleanup")
            # Can't await in __del__, so we schedule it
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.cleanup())
            except RuntimeError:
                pass


try:
    HTTP = AsyncHttpClient()
except Exception as e:
    logger.critical(e)
    sys.exit(1)
