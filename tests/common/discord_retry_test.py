import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from discord.errors import HTTPException

from ironforgedbot.common.discord_retry import (
    DEFAULT_MAX_ATTEMPTS,
    RETRYABLE_DISCORD_HTTP_STATUSES,
    _is_retryable_discord_http_error,
    discord_write_with_retry,
)


def _make_http_exception(status: int, code: int = 0) -> HTTPException:
    """Build an HTTPException with the given HTTP status.

    discord.py's HTTPException.__init__ takes (response, message). The
    message can be a dict whose `code` becomes the Discord-specific error
    code. The response's `.status` becomes the HTTPException `.status`.
    """
    response = Mock()
    response.status = status
    return HTTPException(response, {"code": code, "message": "synthetic"})


class TestIsRetryableDiscordHttpError(unittest.TestCase):
    def test_retryable_statuses_pass(self):
        for status in RETRYABLE_DISCORD_HTTP_STATUSES:
            with self.subTest(status=status):
                self.assertTrue(
                    _is_retryable_discord_http_error(_make_http_exception(status))
                )

    def test_non_retryable_http_status_rejected(self):
        self.assertFalse(_is_retryable_discord_http_error(_make_http_exception(400)))
        self.assertFalse(_is_retryable_discord_http_error(_make_http_exception(403)))
        self.assertFalse(_is_retryable_discord_http_error(_make_http_exception(404)))

    def test_non_http_exception_rejected(self):
        self.assertFalse(_is_retryable_discord_http_error(ValueError("nope")))
        self.assertFalse(_is_retryable_discord_http_error(Exception()))


class TestDiscordWriteWithRetry(unittest.IsolatedAsyncioTestCase):
    async def test_succeeds_on_first_attempt(self):
        factory = AsyncMock()
        await discord_write_with_retry("op", 12345, factory)
        factory.assert_awaited_once()

    async def test_retries_on_503_then_succeeds(self):
        factory = AsyncMock(side_effect=[_make_http_exception(503), None])

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await discord_write_with_retry("op", 12345, factory)

        self.assertEqual(factory.await_count, 2)
        mock_sleep.assert_awaited_once()

    async def test_retries_on_code_zero_then_succeeds(self):
        factory = AsyncMock(side_effect=[_make_http_exception(0), None])

        await discord_write_with_retry("op", 12345, factory)

        self.assertEqual(factory.await_count, 2)

    async def test_does_not_retry_on_forbidden(self):
        from discord.errors import Forbidden

        factory = AsyncMock(side_effect=Forbidden(Mock(), "nope"))

        with self.assertRaises(Forbidden):
            await discord_write_with_retry("op", 12345, factory)

        factory.assert_awaited_once()

    async def test_does_not_retry_on_non_retryable_http_code(self):
        factory = AsyncMock(side_effect=[_make_http_exception(400)])

        with self.assertRaises(HTTPException):
            await discord_write_with_retry("op", 12345, factory)

        factory.assert_awaited_once()

    async def test_gives_up_after_max_attempts_on_persistent_503(self):
        factory = AsyncMock(side_effect=[_make_http_exception(503)] * 10)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with self.assertRaises(HTTPException):
                await discord_write_with_retry("op", 12345, factory)

        self.assertEqual(factory.await_count, DEFAULT_MAX_ATTEMPTS)
        self.assertEqual(mock_sleep.await_count, DEFAULT_MAX_ATTEMPTS - 1)

    async def test_emitter_suppressed_per_attempt(self):
        factory = AsyncMock(side_effect=[_make_http_exception(503), None])

        with patch(
            "ironforgedbot.common.discord_retry.member_update_emitter"
        ) as mock_emitter:
            await discord_write_with_retry("op", 12345, factory)

        self.assertEqual(mock_emitter.suppress_next_for.call_count, 2)

    async def test_suppress_emitter_false_skips_suppression(self):
        factory = AsyncMock(side_effect=[_make_http_exception(503), None])

        with patch(
            "ironforgedbot.common.discord_retry.member_update_emitter"
        ) as mock_emitter:
            await discord_write_with_retry("op", 12345, factory, suppress_emitter=False)

        mock_emitter.suppress_next_for.assert_not_called()
        self.assertEqual(factory.await_count, 2)

    async def test_exponential_backoff_doubles_delay(self):
        factory = AsyncMock(side_effect=[_make_http_exception(503)] * 3)

        with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
            with self.assertRaises(HTTPException):
                await discord_write_with_retry("op", 12345, factory)

        delays = [call.args[0] for call in mock_sleep.await_args_list]
        self.assertEqual(delays, [1, 2])

    async def test_sleep_actually_invoked(self):
        factory = AsyncMock(side_effect=[_make_http_exception(503), None])

        real_sleep = asyncio.sleep

        async def fast_sleep(_):
            await real_sleep(0)

        with patch("ironforgedbot.common.discord_retry.asyncio.sleep", new=fast_sleep):
            await discord_write_with_retry("op", 12345, factory)

        self.assertEqual(factory.await_count, 2)
