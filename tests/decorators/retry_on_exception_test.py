import unittest
from unittest.mock import MagicMock, patch

from ironforgedbot.decorators.retry_on_exception import retry_on_exception


class TestRetryOnExceptionDecorator(unittest.IsolatedAsyncioTestCase):
    def create_retry_func(self, fail_count=0, success_msg="Success!"):
        """Helper to create a function that fails a specified number of times."""

        async def func():
            if not hasattr(func, "call_count"):
                func.call_count = 0
            func.call_count += 1

            if func.call_count <= fail_count:
                raise Exception("Test Exception")
            return success_msg

        return func

    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception(self, mock_sleep):
        msg = "Success!"
        func = self.create_retry_func(fail_count=0, success_msg=msg)

        decorated_func = retry_on_exception(3)(func)
        result = await decorated_func()

        self.assertEqual(result, msg)
        self.assertEqual(func.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("ironforgedbot.decorators.retry_on_exception.logger", new_callable=MagicMock)
    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_retries(self, mock_sleep, mock_logger):
        func = self.create_retry_func(fail_count=2, success_msg="Success!")

        decorated_func = retry_on_exception(3)(func)
        result = await decorated_func()

        self.assertEqual(result, "Success!")
        self.assertEqual(func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_logger.warning.assert_called()

    @patch("ironforgedbot.decorators.retry_on_exception.logger", new_callable=MagicMock)
    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_raises_after_max_retries(
        self, mock_sleep, mock_logger
    ):
        func = self.create_retry_func(fail_count=10)  # Always fails

        decorated_func = retry_on_exception(3)(func)

        with self.assertRaises(Exception) as context:
            await decorated_func()

        self.assertEqual(str(context.exception), "Test Exception")
        self.assertEqual(func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_logger.critical.assert_called_once()

    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_exponential_sleep_between_tries(self, mock_sleep):
        func = self.create_retry_func(fail_count=10)  # Always fails

        decorated_func = retry_on_exception(retries=5)(func)

        with self.assertRaises(Exception):
            await decorated_func()

        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)
        mock_sleep.assert_any_call(8)
