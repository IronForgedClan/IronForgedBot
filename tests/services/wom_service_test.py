import asyncio
import unittest
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from types import SimpleNamespace

import wom
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMembership, GroupMemberGains

from ironforgedbot.services.wom_service import (
    ErrorType,
    WomService,
    WomServiceError,
    WomServiceManager,
    get_wom_service,
    reset_wom_service,
)


class TestErrorType(unittest.TestCase):
    """Test the ErrorType enum."""

    def test_error_type_values(self):
        """Test that ErrorType enum has correct values."""
        self.assertEqual(ErrorType.JSON_MALFORMED.value, "json_malformed")
        self.assertEqual(ErrorType.RATE_LIMIT.value, "rate_limit")
        self.assertEqual(ErrorType.CONNECTION.value, "connection")
        self.assertEqual(ErrorType.UNKNOWN.value, "unknown")

    def test_error_type_is_enum(self):
        """Test that ErrorType is an Enum."""
        self.assertTrue(issubclass(ErrorType, Enum))

    def test_error_type_members(self):
        """Test that ErrorType has all expected members."""
        expected_members = {"JSON_MALFORMED", "RATE_LIMIT", "CONNECTION", "UNKNOWN"}
        actual_members = set(ErrorType.__members__.keys())
        self.assertEqual(expected_members, actual_members)


class TestWomServiceError(unittest.TestCase):
    """Test the WomServiceError exception class."""

    def test_default_error_type(self):
        """Test that WomServiceError defaults to UNKNOWN error type."""
        error = WomServiceError("Test error")
        self.assertEqual(error.error_type, ErrorType.UNKNOWN)
        self.assertEqual(str(error), "Test error")

    def test_explicit_error_type(self):
        """Test that WomServiceError accepts explicit error type."""
        error = WomServiceError("Rate limit", ErrorType.RATE_LIMIT)
        self.assertEqual(error.error_type, ErrorType.RATE_LIMIT)
        self.assertEqual(str(error), "Rate limit")

    def test_inheritance(self):
        """Test that WomServiceError inherits from Exception."""
        error = WomServiceError("Test")
        self.assertIsInstance(error, Exception)

    def test_all_error_types(self):
        """Test creating error with each error type."""
        for error_type in ErrorType:
            error = WomServiceError(f"Test {error_type.value}", error_type)
            self.assertEqual(error.error_type, error_type)


class TestWomService(unittest.IsolatedAsyncioTestCase):
    """Test the WomService class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.user_agent = "TestAgent"
        self.service = WomService(self.api_key, self.user_agent)

        # Mock WOM client
        self.mock_client = AsyncMock()
        self.mock_groups = AsyncMock()
        self.mock_client.groups = self.mock_groups

        # Sample data
        self.sample_group_detail = SimpleNamespace(
            id=12345,
            name="Test Group",
            memberships=[
                SimpleNamespace(
                    player=SimpleNamespace(id=1, username="Player1"),
                    role=GroupRole.Iron,
                ),
                SimpleNamespace(
                    player=SimpleNamespace(id=2, username="Player2"),
                    role=GroupRole.Mithril,
                ),
            ],
        )

        self.sample_gains = [
            SimpleNamespace(
                player=SimpleNamespace(id=1, username="Player1"),
                data=SimpleNamespace(gained=100000),
            ),
            SimpleNamespace(
                player=SimpleNamespace(id=2, username="Player2"),
                data=SimpleNamespace(gained=200000),
            ),
        ]

    def test_init(self):
        """Test WomService initialization."""
        self.assertEqual(self.service.api_key, self.api_key)
        self.assertEqual(self.service.user_agent, self.user_agent)
        self.assertIsNone(self.service._client)

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_client_creates_new_client(self, mock_client_class):
        """Test that _get_client creates a new client when none exists."""
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        client = await self.service._get_client()

        mock_client_class.assert_called_once_with(
            api_key=self.api_key, user_agent=self.user_agent
        )
        mock_client_instance.start.assert_called_once()
        self.assertEqual(client, mock_client_instance)
        self.assertEqual(self.service._client, mock_client_instance)

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_client_reuses_existing_client(self, mock_client_class):
        """Test that _get_client reuses existing client."""
        mock_client_instance = AsyncMock()
        self.service._client = mock_client_instance

        client = await self.service._get_client()

        mock_client_class.assert_not_called()
        mock_client_instance.start.assert_not_called()
        self.assertEqual(client, mock_client_instance)

    def test_categorize_error_json_malformed(self):
        """Test error categorization for JSON malformed errors."""
        test_cases = [
            "JSON is malformed: unexpected token",
            "invalid character at position 5",
            # Note: "malformed JSON response" doesn't contain the exact trigger phrases
        ]
        for error_msg in test_cases:
            with self.subTest(error_msg=error_msg):
                result = self.service._categorize_error(error_msg)
                self.assertEqual(result, ErrorType.JSON_MALFORMED)

    def test_categorize_error_rate_limit(self):
        """Test error categorization for rate limit errors."""
        test_cases = [
            "Rate limit exceeded",
            "API rate limit reached",
            "Too many requests - rate limit",
        ]
        for error_msg in test_cases:
            with self.subTest(error_msg=error_msg):
                result = self.service._categorize_error(error_msg)
                self.assertEqual(result, ErrorType.RATE_LIMIT)

    def test_categorize_error_connection(self):
        """Test error categorization for connection errors."""
        test_cases = [
            "Connection timeout",
            "Network connection failed",
            "Timeout occurred while connecting",
            "Connection reset by peer",
        ]
        for error_msg in test_cases:
            with self.subTest(error_msg=error_msg):
                result = self.service._categorize_error(error_msg)
                self.assertEqual(result, ErrorType.CONNECTION)

    def test_categorize_error_unknown(self):
        """Test error categorization for unknown errors."""
        test_cases = [
            "Some other error",
            "Unexpected server error",
            "Internal server error",
        ]
        for error_msg in test_cases:
            with self.subTest(error_msg=error_msg):
                result = self.service._categorize_error(error_msg)
                self.assertEqual(result, ErrorType.UNKNOWN)

    def test_get_retry_delay(self):
        """Test retry delay calculation for different error types."""
        test_cases = [
            (ErrorType.JSON_MALFORMED, 0, 1.0),
            (ErrorType.JSON_MALFORMED, 1, 2.0),
            (ErrorType.JSON_MALFORMED, 2, 4.0),
            (ErrorType.RATE_LIMIT, 0, 5.0),
            (ErrorType.RATE_LIMIT, 1, 10.0),
            (ErrorType.RATE_LIMIT, 2, 15.0),
            (ErrorType.CONNECTION, 0, 2.0),
            (ErrorType.CONNECTION, 1, 4.0),
            (ErrorType.CONNECTION, 2, 6.0),
            (ErrorType.UNKNOWN, 0, 0.0),
            (ErrorType.UNKNOWN, 5, 0.0),
        ]

        for error_type, attempt, expected_delay in test_cases:
            with self.subTest(error_type=error_type, attempt=attempt):
                result = self.service._get_retry_delay(error_type, attempt)
                self.assertEqual(result, expected_delay)

    def test_should_retry(self):
        """Test retry decision logic."""
        self.assertTrue(self.service._should_retry(ErrorType.JSON_MALFORMED))
        self.assertTrue(self.service._should_retry(ErrorType.RATE_LIMIT))
        self.assertTrue(self.service._should_retry(ErrorType.CONNECTION))
        self.assertFalse(self.service._should_retry(ErrorType.UNKNOWN))

    async def test_close_with_client(self):
        """Test closing service with active client."""
        mock_client = AsyncMock()
        self.service._client = mock_client

        await self.service.close()

        mock_client.close.assert_called_once()
        self.assertIsNone(self.service._client)

    async def test_close_with_client_error(self):
        """Test closing service when client.close() raises exception."""
        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("Close error")
        self.service._client = mock_client

        with patch("ironforgedbot.services.wom_service.logger") as mock_logger:
            await self.service.close()

        mock_client.close.assert_called_once()
        mock_logger.warning.assert_called_once()
        self.assertIsNone(self.service._client)

    async def test_close_without_client(self):
        """Test closing service without active client."""
        self.service._client = None

        await self.service.close()

        # Should complete without error

    async def test_context_manager(self):
        """Test async context manager functionality."""
        mock_client = AsyncMock()
        self.service._client = mock_client

        async with self.service as service:
            self.assertEqual(service, self.service)

        mock_client.close.assert_called_once()
        self.assertIsNone(self.service._client)

    async def test_context_manager_with_exception(self):
        """Test context manager cleanup on exception."""
        mock_client = AsyncMock()
        self.service._client = mock_client

        with self.assertRaises(ValueError):
            async with self.service:
                raise ValueError("Test error")

        mock_client.close.assert_called_once()
        self.assertIsNone(self.service._client)

    async def test_context_manager_cleanup_error(self):
        """Test context manager when cleanup fails."""
        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("Cleanup error")
        self.service._client = mock_client

        with patch("ironforgedbot.services.wom_service.logger") as mock_logger:
            async with self.service:
                pass

        mock_client.close.assert_called_once()
        mock_logger.warning.assert_called_once()
        self.assertIsNone(self.service._client)


class TestWomServiceRetryLogic(unittest.IsolatedAsyncioTestCase):
    """Test the retry logic in WomService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = WomService("test_key")

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_success_first_attempt(self, mock_sleep):
        """Test successful operation on first attempt."""
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = "success_data"

        async def mock_operation(**kwargs):
            return mock_result

        result = await self.service._execute_with_retry(
            mock_operation, "test_operation", retries=2, test_param="value"
        )

        self.assertEqual(result, "success_data")
        mock_sleep.assert_not_called()

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_wom_result_error(self, mock_sleep):
        """Test handling of WOM result errors."""
        mock_result = Mock()
        mock_result.is_ok = False
        mock_result.unwrap_err.return_value = "WOM API error"

        async def mock_operation(**kwargs):
            return mock_result

        with self.assertRaises(WomServiceError) as cm:
            await self.service._execute_with_retry(
                mock_operation, "test_operation", retries=2
            )

        self.assertIn("Error in test_operation", str(cm.exception))
        mock_sleep.assert_not_called()

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_json_error_with_retry(self, mock_sleep):
        """Test retry logic for JSON malformed errors."""
        call_count = 0

        async def mock_operation(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("JSON is malformed")
            mock_result = Mock()
            mock_result.is_ok = True
            mock_result.unwrap.return_value = "success"
            return mock_result

        result = await self.service._execute_with_retry(
            mock_operation, "test_operation", retries=3
        )

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        # Check exponential backoff: 1s, 2s
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_rate_limit_with_retry(self, mock_sleep):
        """Test retry logic for rate limit errors."""
        call_count = 0

        async def mock_operation(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("rate limit exceeded")
            mock_result = Mock()
            mock_result.is_ok = True
            mock_result.unwrap.return_value = "success"
            return mock_result

        result = await self.service._execute_with_retry(
            mock_operation, "test_operation", retries=3
        )

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        # Check linear increase: 5s, 10s
        mock_sleep.assert_any_call(5.0)
        mock_sleep.assert_any_call(10.0)

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_connection_error_with_retry(self, mock_sleep):
        """Test retry logic for connection errors."""
        call_count = 0

        async def mock_operation(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("connection timeout")
            mock_result = Mock()
            mock_result.is_ok = True
            mock_result.unwrap.return_value = "success"
            return mock_result

        result = await self.service._execute_with_retry(
            mock_operation, "test_operation", retries=3
        )

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        # Check linear increase: 2s, 4s
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_unknown_error_no_retry(self, mock_sleep):
        """Test that unknown errors are not retried."""
        async def mock_operation(**kwargs):
            raise Exception("some unknown error")

        with self.assertRaises(WomServiceError) as cm:
            await self.service._execute_with_retry(
                mock_operation, "test_operation", retries=3
            )

        self.assertEqual(cm.exception.error_type, ErrorType.UNKNOWN)
        mock_sleep.assert_not_called()

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_execute_with_retry_max_retries_reached(self, mock_sleep):
        """Test behavior when max retries are reached."""
        async def mock_operation(**kwargs):
            raise Exception("JSON is malformed")

        with self.assertRaises(WomServiceError) as cm:
            await self.service._execute_with_retry(
                mock_operation, "test_operation", retries=2
            )

        self.assertEqual(cm.exception.error_type, ErrorType.JSON_MALFORMED)
        self.assertIn("invalid data format", str(cm.exception))
        self.assertEqual(mock_sleep.call_count, 2)


class TestWomServiceMethods(unittest.IsolatedAsyncioTestCase):
    """Test WomService public methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = WomService("test_key")
        self.mock_client = AsyncMock()
        self.service._client = self.mock_client

        # Sample data
        self.sample_group_detail = SimpleNamespace(
            id=12345,
            name="Test Group",
            memberships=[
                SimpleNamespace(
                    player=SimpleNamespace(id=1, username="Player1"),
                    role=GroupRole.Iron,
                ),
            ],
        )

        self.sample_gains = [
            SimpleNamespace(
                player=SimpleNamespace(id=1, username="Player1"),
                data=SimpleNamespace(gained=100000),
            ),
        ]

    async def test_get_group_details_success(self):
        """Test successful group details retrieval."""
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = self.sample_group_detail
        self.mock_client.groups.get_details.return_value = mock_result

        result = await self.service.get_group_details(12345)

        self.assertEqual(result, self.sample_group_detail)
        self.mock_client.groups.get_details.assert_called_once_with(12345)

    async def test_get_group_details_with_retries(self):
        """Test group details retrieval with custom retry count."""
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = self.sample_group_detail
        self.mock_client.groups.get_details.return_value = mock_result

        result = await self.service.get_group_details(12345, retries=5)

        self.assertEqual(result, self.sample_group_detail)

    async def test_get_group_gains_success(self):
        """Test successful group gains retrieval."""
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = self.sample_gains
        self.mock_client.groups.get_gains.return_value = mock_result

        result = await self.service.get_group_gains(
            12345, metric=Metric.Attack, period=Period.Week, limit=100, offset=50
        )

        self.assertEqual(result, self.sample_gains)
        self.mock_client.groups.get_gains.assert_called_once_with(
            12345, metric=Metric.Attack, period=Period.Week, limit=100, offset=50
        )

    async def test_get_group_gains_default_parameters(self):
        """Test group gains retrieval with default parameters."""
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = self.sample_gains
        self.mock_client.groups.get_gains.return_value = mock_result

        result = await self.service.get_group_gains(12345)

        self.assertEqual(result, self.sample_gains)
        self.mock_client.groups.get_gains.assert_called_once_with(
            12345, metric=Metric.Overall, period=Period.Month, limit=50, offset=0
        )

    @patch("ironforgedbot.services.wom_service.logger")
    async def test_get_all_group_gains_single_page(self, mock_logger):
        """Test get_all_group_gains with single page of results."""
        gains_page = [
            SimpleNamespace(player=SimpleNamespace(id=i), data=SimpleNamespace(gained=i * 1000))
            for i in range(1, 31)  # 30 items, less than limit of 50
        ]

        with patch.object(self.service, 'get_group_gains', return_value=gains_page) as mock_get_gains:
            result = await self.service.get_all_group_gains(12345, limit=50)

        self.assertEqual(len(result), 30)
        self.assertEqual(result, gains_page)
        mock_get_gains.assert_called_once_with(
            group_id=12345,
            metric=Metric.Overall,
            period=Period.Month,
            limit=50,
            offset=0,
        )
        mock_logger.info.assert_called_with(
            "Retrieved 30 total gains across 0 requests"
        )

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    @patch("ironforgedbot.services.wom_service.logger")
    async def test_get_all_group_gains_multiple_pages(self, mock_logger, mock_sleep):
        """Test get_all_group_gains with multiple pages."""
        # First page: full 50 items
        page1 = [SimpleNamespace(player=SimpleNamespace(id=i), data=SimpleNamespace(gained=i * 1000)) for i in range(1, 51)]
        # Second page: 30 items (less than limit, so end of data)
        page2 = [SimpleNamespace(player=SimpleNamespace(id=i), data=SimpleNamespace(gained=i * 1000)) for i in range(51, 81)]

        call_count = 0
        async def mock_get_gains(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return page1
            elif call_count == 2:
                return page2

        with patch.object(self.service, 'get_group_gains', side_effect=mock_get_gains) as mock_get_gains_patch:
            result = await self.service.get_all_group_gains(12345, limit=50)

        self.assertEqual(len(result), 80)
        self.assertEqual(result, page1 + page2)
        self.assertEqual(mock_get_gains_patch.call_count, 2)

        # Check call arguments
        expected_calls = [
            {
                'group_id': 12345,
                'metric': Metric.Overall,
                'period': Period.Month,
                'limit': 50,
                'offset': 0,
            },
            {
                'group_id': 12345,
                'metric': Metric.Overall,
                'period': Period.Month,
                'limit': 50,
                'offset': 50,
            },
        ]

        for i, call in enumerate(mock_get_gains_patch.call_args_list):
            self.assertEqual(call.kwargs, expected_calls[i])

        mock_sleep.assert_not_called()  # No sleep for first few iterations
        mock_logger.info.assert_called_with("Retrieved 80 total gains across 1 requests")

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    @patch("ironforgedbot.services.wom_service.logger")
    async def test_get_all_group_gains_with_delay(self, mock_logger, mock_sleep):
        """Test get_all_group_gains includes delay every 5 requests."""
        # Create 6 pages of full results to trigger the delay logic
        full_page = [SimpleNamespace(player=SimpleNamespace(id=i), data=SimpleNamespace(gained=1000)) for i in range(50)]

        call_count = 0
        async def mock_get_gains(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 6:
                return full_page
            return []  # Empty to end pagination

        with patch.object(self.service, 'get_group_gains', side_effect=mock_get_gains):
            result = await self.service.get_all_group_gains(12345, limit=50)

        self.assertEqual(len(result), 300)  # 6 pages * 50 items
        mock_sleep.assert_called_once_with(0.1)  # Delay after 5th iteration
        mock_logger.debug.assert_called_with(
            "Processed 5 pagination requests, total gains: 250"
        )

    @patch("ironforgedbot.services.wom_service.logger")
    async def test_get_all_group_gains_empty_response(self, mock_logger):
        """Test get_all_group_gains with empty response."""
        with patch.object(self.service, 'get_group_gains', return_value=[]):
            result = await self.service.get_all_group_gains(12345)

        self.assertEqual(result, [])
        mock_logger.info.assert_any_call("Received empty gains response, ending pagination")

    @patch("ironforgedbot.services.wom_service.logger")
    async def test_get_all_group_gains_max_iterations(self, mock_logger):
        """Test get_all_group_gains hits max iterations limit."""
        full_page = [SimpleNamespace(player=SimpleNamespace(id=i), data=SimpleNamespace(gained=1000)) for i in range(50)]

        with patch.object(self.service, 'get_group_gains', return_value=full_page):
            result = await self.service.get_all_group_gains(12345, max_iterations=3)

        self.assertEqual(len(result), 150)  # 3 pages * 50 items
        mock_logger.warning.assert_called_with(
            "Pagination safety limit reached (3 iterations), may have incomplete data"
        )

    @patch("ironforgedbot.services.wom_service.logger")
    async def test_get_group_members_with_roles_success(self, mock_logger):
        """Test successful group members with roles filtering."""
        group_detail = SimpleNamespace(
            memberships=[
                SimpleNamespace(
                    player=SimpleNamespace(username="Player1"),
                    role=GroupRole.Iron,
                ),
                SimpleNamespace(
                    player=SimpleNamespace(username="Player2"),
                    role=GroupRole.Helper,
                ),
                SimpleNamespace(
                    player=SimpleNamespace(username="Player3"),
                    role=GroupRole.Mithril,
                ),
                SimpleNamespace(
                    player=SimpleNamespace(username="Player4"),
                    role=None,
                ),
            ]
        )

        with patch.object(self.service, 'get_group_details', return_value=group_detail):
            valid, ignored = await self.service.get_group_members_with_roles(
                12345, ignored_roles=[GroupRole.Helper]
            )

        self.assertEqual(valid, ["Player1", "Player3"])
        self.assertEqual(ignored, ["Player2"])
        mock_logger.info.assert_any_call("Player4 has no role, skipping.")
        mock_logger.info.assert_any_call("Player2 has ignored role helper, adding to ignored list.")

    async def test_get_group_members_with_roles_no_ignored_roles(self):
        """Test group members filtering with no ignored roles."""
        group_detail = SimpleNamespace(
            memberships=[
                SimpleNamespace(
                    player=SimpleNamespace(username="Player1"),
                    role=GroupRole.Iron,
                ),
                SimpleNamespace(
                    player=SimpleNamespace(username="Player2"),
                    role=GroupRole.Helper,
                ),
            ]
        )

        with patch.object(self.service, 'get_group_details', return_value=group_detail):
            valid, ignored = await self.service.get_group_members_with_roles(12345)

        self.assertEqual(valid, ["Player1", "Player2"])
        self.assertEqual(ignored, [])


class TestWomServiceManager(unittest.IsolatedAsyncioTestCase):
    """Test the WomServiceManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = WomServiceManager()

    def test_init(self):
        """Test WomServiceManager initialization."""
        self.assertIsNone(self.manager._instance)
        self.assertIsNone(self.manager._api_key)

    def test_initialize_new_service(self):
        """Test initializing a new service."""
        service = self.manager.initialize("test_key", "TestAgent")

        self.assertIsInstance(service, WomService)
        self.assertEqual(service.api_key, "test_key")
        self.assertEqual(service.user_agent, "TestAgent")
        self.assertEqual(self.manager._instance, service)
        self.assertEqual(self.manager._api_key, "test_key")

    async def test_initialize_replaces_existing_service(self):
        """Test that initializing replaces an existing service."""
        # Create first service
        first_service = self.manager.initialize("key1")

        # Mock the close method to avoid coroutine warnings
        with patch.object(first_service, 'close', new_callable=AsyncMock):
            # Create second service
            second_service = self.manager.initialize("key2")

            self.assertNotEqual(first_service, second_service)
            self.assertEqual(self.manager._instance, second_service)
            self.assertEqual(self.manager._api_key, "key2")

    def test_get_service_success(self):
        """Test getting service when initialized."""
        service = self.manager.initialize("test_key")
        retrieved_service = self.manager.get_service()

        self.assertEqual(service, retrieved_service)

    def test_get_service_not_initialized(self):
        """Test getting service when not initialized."""
        with self.assertRaises(ValueError) as cm:
            self.manager.get_service()

        self.assertIn("WOM service not initialized", str(cm.exception))

    def test_is_initialized(self):
        """Test is_initialized method."""
        self.assertFalse(self.manager.is_initialized())

        self.manager.initialize("test_key")
        self.assertTrue(self.manager.is_initialized())

    async def test_close_with_service(self):
        """Test closing manager with active service."""
        service = self.manager.initialize("test_key")
        mock_close = AsyncMock()
        service.close = mock_close

        await self.manager.close()

        mock_close.assert_called_once()
        self.assertIsNone(self.manager._instance)
        self.assertIsNone(self.manager._api_key)

    async def test_close_without_service(self):
        """Test closing manager without active service."""
        await self.manager.close()

        # Should complete without error
        self.assertIsNone(self.manager._instance)
        self.assertIsNone(self.manager._api_key)


class TestModuleFunctions(unittest.TestCase):
    """Test module-level functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset the global manager before each test
        reset_wom_service()

    def tearDown(self):
        """Clean up after each test."""
        reset_wom_service()

    def test_get_wom_service_first_call_with_key(self):
        """Test first call to get_wom_service with API key."""
        service = get_wom_service("test_key")

        self.assertIsInstance(service, WomService)
        self.assertEqual(service.api_key, "test_key")

    def test_get_wom_service_first_call_without_key(self):
        """Test first call to get_wom_service without API key."""
        with self.assertRaises(ValueError) as cm:
            get_wom_service()

        self.assertIn("API key required", str(cm.exception))

    def test_get_wom_service_subsequent_calls(self):
        """Test subsequent calls return same instance."""
        service1 = get_wom_service("test_key")
        service2 = get_wom_service()
        service3 = get_wom_service("different_key")  # Should still return same instance

        self.assertEqual(service1, service2)
        self.assertEqual(service2, service3)

    def test_reset_wom_service_sync(self):
        """Test reset_wom_service in synchronous context."""
        get_wom_service("test_key")

        reset_wom_service()

        # Should require API key again after reset
        with self.assertRaises(ValueError):
            get_wom_service()

    def test_reset_wom_service_always_sync(self):
        """Test reset_wom_service always uses synchronous cleanup."""
        get_wom_service("test_key")

        # Should not raise error regardless of async context
        reset_wom_service()

        # Should require API key again after reset
        with self.assertRaises(ValueError):
            get_wom_service()


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for WomService."""

    def setUp(self):
        """Set up test fixtures."""
        reset_wom_service()

    def tearDown(self):
        """Clean up after each test."""
        reset_wom_service()

    async def test_full_workflow_with_context_manager(self):
        """Test full workflow using context manager."""
        with patch("ironforgedbot.services.wom_service.wom.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock group details response
            mock_details_result = Mock()
            mock_details_result.is_ok = True
            mock_details_result.unwrap.return_value = SimpleNamespace(
                id=12345,
                memberships=[
                    SimpleNamespace(
                        player=SimpleNamespace(username="TestPlayer"),
                        role=GroupRole.Iron,
                    )
                ]
            )
            mock_client.groups.get_details.return_value = mock_details_result

            # Mock gains response
            mock_gains_result = Mock()
            mock_gains_result.is_ok = True
            mock_gains_result.unwrap.return_value = [
                SimpleNamespace(
                    player=SimpleNamespace(username="TestPlayer"),
                    data=SimpleNamespace(gained=50000),
                )
            ]
            mock_client.groups.get_gains.return_value = mock_gains_result

            async with get_wom_service("test_key") as service:
                # Test group details
                group_details = await service.get_group_details(12345)
                self.assertEqual(group_details.id, 12345)

                # Test gains
                gains = await service.get_group_gains(12345)
                self.assertEqual(len(gains), 1)
                self.assertEqual(gains[0].player.username, "TestPlayer")

                # Test members with roles
                valid, ignored = await service.get_group_members_with_roles(12345)
                self.assertEqual(valid, ["TestPlayer"])
                self.assertEqual(ignored, [])

            # Verify client was properly closed
            mock_client.close.assert_called_once()

    async def test_error_propagation(self):
        """Test that errors are properly propagated through the system."""
        with patch("ironforgedbot.services.wom_service.wom.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock a WOM API error
            mock_result = Mock()
            mock_result.is_ok = False
            mock_result.unwrap_err.return_value = "Group not found"
            mock_client.groups.get_details.return_value = mock_result

            service = get_wom_service("test_key")

            with self.assertRaises(WomServiceError) as cm:
                await service.get_group_details(12345)

            self.assertIn("Error in get_group_details", str(cm.exception))
            self.assertEqual(cm.exception.error_type, ErrorType.UNKNOWN)

    async def test_service_lifecycle(self):
        """Test service lifecycle management."""
        # Get service
        service1 = get_wom_service("test_key")
        self.assertIsNotNone(service1)

        # Get same service
        service2 = get_wom_service()
        self.assertEqual(service1, service2)

        # Reset and get new service
        reset_wom_service()

        # After reset, should require API key again
        with self.assertRaises(ValueError):
            get_wom_service()

        # Create new service
        service3 = get_wom_service("new_key")
        self.assertEqual(service3.api_key, "new_key")

        # Ensure proper cleanup for tearDown
        reset_wom_service()


if __name__ == "__main__":
    unittest.main()