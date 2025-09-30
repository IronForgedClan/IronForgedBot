import unittest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

from ironforgedbot.services.wom_service import (
    WomService,
    WomServiceError,
    WomRateLimitError,
    WomTimeoutError,
    get_wom_service,
)


class TestWomService(unittest.IsolatedAsyncioTestCase):
    """Test the WomService class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock CONFIG to have valid values
        self.config_patcher = patch("ironforgedbot.services.wom_service.CONFIG")
        self.mock_config = self.config_patcher.start()
        self.mock_config.WOM_API_KEY = "test_api_key"
        self.mock_config.WOM_GROUP_ID = 12345

    def tearDown(self):
        """Clean up after tests."""
        self.config_patcher.stop()

    def test_init_with_valid_config(self):
        """Test WomService initialization with valid configuration."""
        service = WomService()
        self.assertEqual(service.api_key, "test_api_key")
        self.assertEqual(service.group_id, 12345)
        self.assertIsNone(service._client)

    def test_init_with_missing_api_key(self):
        """Test WomService initialization with missing API key."""
        self.mock_config.WOM_API_KEY = ""

        with self.assertRaises(WomServiceError) as cm:
            WomService()

        self.assertIn("WOM_API_KEY not configured", str(cm.exception))

    async def test_context_manager(self):
        """Test async context manager functionality."""
        service = WomService()
        service.close = AsyncMock()

        async with service as ctx_service:
            self.assertEqual(ctx_service, service)

        service.close.assert_called_once()

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_monthly_activity_data_success(self, mock_client_class):
        """Test successful monthly activity data retrieval."""
        # Mock WOM client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Mock group details result
        mock_group_result = Mock()
        mock_group_result.is_ok = True
        mock_group_details = SimpleNamespace(
            id=12345,
            memberships=[SimpleNamespace(player=SimpleNamespace(username="Player1"))],
        )
        mock_group_result.unwrap.return_value = mock_group_details
        mock_client.groups.get_details.return_value = mock_group_result

        # Mock gains result
        mock_gains_result = Mock()
        mock_gains_result.is_ok = True
        mock_gains = [SimpleNamespace(player=SimpleNamespace(username="Player1"))]
        mock_gains_result.unwrap.return_value = mock_gains
        mock_client.groups.get_gains.return_value = mock_gains_result

        service = WomService()

        group_details, member_gains = await service.get_monthly_activity_data()

        self.assertEqual(group_details, mock_group_details)
        self.assertEqual(member_gains, mock_gains)

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_monthly_activity_data_rate_limit_error(self, mock_client_class):
        """Test rate limit error handling."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Mock rate limit error
        mock_result = Mock()
        mock_result.is_ok = False
        mock_result.unwrap_err.return_value = "Rate limit exceeded"
        mock_client.groups.get_details.return_value = mock_result

        service = WomService()

        with self.assertRaises(WomServiceError):
            await service.get_monthly_activity_data()

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_group_membership_data_success(self, mock_client_class):
        """Test successful group membership data retrieval."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_result = Mock()
        mock_result.is_ok = True
        mock_group_details = SimpleNamespace(
            id=12345,
            memberships=[SimpleNamespace(player=SimpleNamespace(username="Player1"))],
        )
        mock_result.unwrap.return_value = mock_group_details
        mock_client.groups.get_details.return_value = mock_result

        service = WomService()

        result = await service.get_group_membership_data()

        self.assertEqual(result, mock_group_details)

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_player_name_history_success(self, mock_client_class):
        """Test successful player name history retrieval."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.is_err = False  # Explicitly set this
        mock_name_changes = [SimpleNamespace(old_name="OldName", new_name="NewName")]
        mock_result.unwrap.return_value = mock_name_changes
        mock_client.players.get_name_changes.return_value = mock_result

        service = WomService()

        result = await service.get_player_name_history("TestPlayer")

        self.assertEqual(result, mock_name_changes)
        mock_client.players.get_name_changes.assert_called_once_with("TestPlayer")

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_player_name_history_error(self, mock_client_class):
        """Test player name history error handling."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_result = Mock()
        mock_result.is_ok = False
        mock_result.is_err = True  # Explicitly set this
        mock_result.unwrap_err.return_value = "Player not found"
        mock_client.players.get_name_changes.return_value = mock_result

        service = WomService()

        with self.assertRaises(WomServiceError) as cm:
            await service.get_player_name_history("TestPlayer")

        self.assertIn("Failed to get name history", str(cm.exception))

    async def test_close_with_client(self):
        """Test closing service with active client."""
        mock_client = AsyncMock()
        service = WomService()
        service._client = mock_client

        await service.close()

        mock_client.close.assert_called_once()
        self.assertIsNone(service._client)

    async def test_close_with_client_error(self):
        """Test closing service when close() raises exception."""
        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("Close error")
        service = WomService()
        service._client = mock_client

        with patch("ironforgedbot.services.wom_service.logger") as mock_logger:
            await service.close()

        mock_client.close.assert_called_once()
        mock_logger.warning.assert_called_once()
        self.assertIsNone(service._client)

    async def test_close_without_client(self):
        """Test closing service without active client."""
        service = WomService()
        service._client = None

        # Should complete without error
        await service.close()


class TestGetWomService(unittest.TestCase):
    """Test the get_wom_service function."""

    @patch("ironforgedbot.services.wom_service.CONFIG")
    def test_get_wom_service_success(self, mock_config):
        """Test successful service creation."""
        mock_config.WOM_API_KEY = "test_key"
        mock_config.WOM_GROUP_ID = 12345

        service = get_wom_service()

        self.assertIsInstance(service, WomService)
        self.assertEqual(service.api_key, "test_key")
        self.assertEqual(service.group_id, 12345)

    @patch("ironforgedbot.services.wom_service.CONFIG")
    def test_get_wom_service_missing_config(self, mock_config):
        """Test service creation with missing configuration."""
        mock_config.WOM_API_KEY = ""
        mock_config.WOM_GROUP_ID = 12345

        with self.assertRaises(WomServiceError):
            get_wom_service()


class TestWomServiceExceptions(unittest.TestCase):
    """Test WOM service exception hierarchy."""

    def test_exception_hierarchy(self):
        """Test that custom exceptions inherit properly."""
        self.assertTrue(issubclass(WomRateLimitError, WomServiceError))
        self.assertTrue(issubclass(WomTimeoutError, WomServiceError))
        self.assertTrue(issubclass(WomServiceError, Exception))

    def test_exception_creation(self):
        """Test creating custom exceptions."""
        base_error = WomServiceError("Base error")
        self.assertEqual(str(base_error), "Base error")

        rate_limit_error = WomRateLimitError("Rate limit")
        self.assertEqual(str(rate_limit_error), "Rate limit")

        timeout_error = WomTimeoutError("Timeout")
        self.assertEqual(str(timeout_error), "Timeout")


if __name__ == "__main__":
    unittest.main()
