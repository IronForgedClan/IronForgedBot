import logging
import sys
from typing import Any, TypedDict
import asyncio

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
        self._session_lock = asyncio.Lock()

        event_emitter.on("shutdown", self.cleanup, priority=20)

    async def _initialize_session(self):
        """Initialize the aiohttp session with proper configuration."""
        async with self._session_lock:
            if not self.session or self.session.closed:
                logger.debug("Initializing new HTTP session")

                timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)

                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300,
                    use_dns_cache=True,
                    enable_cleanup_closed=True,
                )

                self.session = aiohttp.ClientSession(
                    timeout=timeout, connector=connector, raise_for_status=False
                )

    @retry_on_exception(retries=5)
    async def get(self, url, params=None, headers=None, json_data=None) -> HttpResponse:
        """Make a request to the provided URL with the given parameters."""
        try:
            await self._initialize_session()
            assert self.session

            async with self.session.get(
                url, params=params, headers=headers, json=json_data
            ) as response:
                if response.status >= 500:
                    error_text = await response.text()
                    logger.error(
                        f"Server error {response.status} for {url}: {error_text[:200]}"
                    )
                    raise HttpException(
                        f"A remote server error occurred: {response.status}"
                    )

                if response.status == 408:
                    logger.warning(f"Request timeout (408) for {url}")
                    raise HttpException(
                        f"No response from remote server: {response.status}"
                    )

                if response.status == 429:
                    logger.warning(f"Rate limited (429) for {url}")
                    raise HttpException(
                        f"Rate limited or timed out response: {response.status}"
                    )

                content_type = response.content_type.lower()

                try:
                    if "json" in content_type:
                        data = await response.json()
                    elif "text" in content_type or "html" in content_type:
                        text_data = await response.text()
                        # Official hiscores api doesn't correctly report content type
                        # it returns json data while reporting plaintext content.
                        # Fallback to raw text only if json parsing fails.
                        try:
                            import json

                            data = json.loads(text_data)
                        except (json.JSONDecodeError, ValueError):
                            data = text_data
                    else:
                        data = await response.read()
                except Exception as e:
                    logger.error(f"Error reading response body from {url}: {e}")
                    raise HttpException(f"Failed to read response data: {e}")

                return HttpResponse(status=response.status, body=data)

        except (aiohttp.ServerTimeoutError, aiohttp.ConnectionTimeoutError, aiohttp.SocketTimeoutError) as e:
            logger.error(f"Timeout error for {url}: {e}")
            raise HttpException(f"Request timed out: {e}")
        except aiohttp.ClientConnectionError as e:
            logger.error(f"Connection error for {url}: {e}")
            raise HttpException(f"Connection failed: {e}")
        except aiohttp.ClientError as e:
            logger.error(f"Client error for {url}: {e}")
            raise HttpException(f"HTTP client error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}", exc_info=True)
            raise HttpException(f"Unexpected error: {e}")

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
        """Cleanup the HTTP session and connector."""
        async with self._session_lock:
            if self.session and not self.session.closed:
                logger.debug("Closing HTTP session")
                try:
                    await self.session.close()
                    # Wait a bit for the underlying connections to close
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error during session cleanup: {e}")
                finally:
                    self.session = None

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
