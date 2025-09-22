import unittest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

import wom
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMemberGains

from ironforgedbot.services.wom_service import (
    WomClient,
    WomServiceError,
    get_wom_client,
)


class TestWomClient(unittest.IsolatedAsyncioTestCase):
    """Test the WomClient class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock CONFIG to have valid values
        self.config_patcher = patch('ironforgedbot.services.wom_service.CONFIG')
        self.mock_config = self.config_patcher.start()
        self.mock_config.WOM_API_KEY = "test_api_key"
        self.mock_config.WOM_GROUP_ID = 12345

    def tearDown(self):
        """Clean up after tests."""
        self.config_patcher.stop()

    def test_init_with_valid_config(self):
        """Test WomClient initialization with valid configuration."""
        client = WomClient()
        self.assertEqual(client.api_key, "test_api_key")
        self.assertEqual(client.group_id, 12345)
        self.assertIsNone(client._client)

    def test_init_with_missing_api_key(self):
        """Test WomClient initialization with missing API key."""
        self.mock_config.WOM_API_KEY = ""

        with self.assertRaises(WomServiceError) as cm:
            WomClient()

        self.assertIn("WOM_API_KEY not configured", str(cm.exception))

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_client_creates_new_client(self, mock_client_class):
        """Test that _get_client creates a new client when none exists."""
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        client = WomClient()
        result = await client._get_client()

        mock_client_class.assert_called_once_with(
            api_key="test_api_key", user_agent="IronForged"
        )
        mock_client_instance.start.assert_called_once()
        self.assertEqual(result, mock_client_instance)
        self.assertEqual(client._client, mock_client_instance)

    @patch("ironforgedbot.services.wom_service.wom.Client")
    async def test_get_client_reuses_existing_client(self, mock_client_class):
        """Test that _get_client reuses existing client."""
        mock_client_instance = AsyncMock()
        client = WomClient()
        client._client = mock_client_instance

        result = await client._get_client()

        mock_client_class.assert_not_called()
        mock_client_instance.start.assert_not_called()
        self.assertEqual(result, mock_client_instance)

    async def test_close_with_client(self):
        """Test closing client with active connection."""
        mock_client = AsyncMock()
        client = WomClient()
        client._client = mock_client

        await client.close()

        mock_client.close.assert_called_once()
        self.assertIsNone(client._client)

    async def test_close_with_client_error(self):
        """Test closing client when close() raises exception."""
        mock_client = AsyncMock()
        mock_client.close.side_effect = Exception("Close error")
        client = WomClient()
        client._client = mock_client

        with patch("ironforgedbot.services.wom_service.logger") as mock_logger:
            await client.close()

        mock_client.close.assert_called_once()
        mock_logger.warning.assert_called_once()
        self.assertIsNone(client._client)

    async def test_close_without_client(self):
        """Test closing client without active connection."""
        client = WomClient()
        client._client = None

        # Should complete without error
        await client.close()

    async def test_context_manager(self):
        """Test async context manager functionality."""
        mock_client = AsyncMock()
        client = WomClient()
        client._client = mock_client

        async with client as ctx_client:
            self.assertEqual(ctx_client, client)

        mock_client.close.assert_called_once()

    async def test_get_group_details_success(self):
        """Test successful group details retrieval."""
        mock_wom_client = AsyncMock()
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = SimpleNamespace(id=12345, name="Test Group")
        mock_wom_client.groups.get_details.return_value = mock_result

        client = WomClient()
        client._client = mock_wom_client

        result = await client.get_group_details(12345)

        self.assertEqual(result.id, 12345)
        self.assertEqual(result.name, "Test Group")
        mock_wom_client.groups.get_details.assert_called_once_with(12345)

    async def test_get_group_details_default_group_id(self):
        """Test group details retrieval with default group ID."""
        mock_wom_client = AsyncMock()
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = SimpleNamespace(id=12345, name="Test Group")
        mock_wom_client.groups.get_details.return_value = mock_result

        client = WomClient()
        client._client = mock_wom_client

        result = await client.get_group_details()  # No group_id provided

        mock_wom_client.groups.get_details.assert_called_once_with(12345)  # Uses default

    async def test_get_group_details_api_error(self):
        """Test group details retrieval with API error."""
        mock_wom_client = AsyncMock()
        mock_result = Mock()
        mock_result.is_ok = False
        mock_result.unwrap_err.return_value = "Group not found"
        mock_wom_client.groups.get_details.return_value = mock_result

        client = WomClient()
        client._client = mock_wom_client

        with self.assertRaises(WomServiceError) as cm:
            await client.get_group_details(12345)

        self.assertIn("WOM API error: Group not found", str(cm.exception))

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_get_group_details_retry_on_connection_error(self, mock_sleep):
        """Test retry logic for connection errors."""
        mock_wom_client = AsyncMock()
        mock_wom_client.groups.get_details.side_effect = [
            Exception("Connection timeout"),
            Mock(is_ok=True, unwrap=lambda: SimpleNamespace(id=12345))
        ]

        client = WomClient()
        client._client = mock_wom_client

        result = await client.get_group_details(12345)

        self.assertEqual(result.id, 12345)
        self.assertEqual(mock_wom_client.groups.get_details.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    async def test_get_group_gains_success(self):
        """Test successful group gains retrieval."""
        mock_wom_client = AsyncMock()
        mock_result = Mock()
        mock_result.is_ok = True
        mock_gains = [SimpleNamespace(player=SimpleNamespace(username="Player1"))]
        mock_result.unwrap.return_value = mock_gains
        mock_wom_client.groups.get_gains.return_value = mock_result

        client = WomClient()
        client._client = mock_wom_client

        result = await client.get_group_gains(
            12345, metric=Metric.Attack, period=Period.Week, limit=100, offset=50
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].player.username, "Player1")
        mock_wom_client.groups.get_gains.assert_called_once_with(
            12345, metric=Metric.Attack, period=Period.Week, limit=100, offset=50
        )

    async def test_get_group_gains_default_parameters(self):
        """Test group gains retrieval with default parameters."""
        mock_wom_client = AsyncMock()
        mock_result = Mock()
        mock_result.is_ok = True
        mock_result.unwrap.return_value = []
        mock_wom_client.groups.get_gains.return_value = mock_result

        client = WomClient()
        client._client = mock_wom_client

        await client.get_group_gains()  # Use all defaults

        mock_wom_client.groups.get_gains.assert_called_once_with(
            12345, metric=Metric.Overall, period=Period.Month, limit=50, offset=0
        )

    async def test_get_all_group_gains_single_page(self):
        """Test get_all_group_gains with single page of results."""
        gains_page = [
            SimpleNamespace(player=SimpleNamespace(username=f"Player{i}"))
            for i in range(1, 31)  # 30 items, less than limit of 50
        ]

        client = WomClient()
        with patch.object(client, 'get_group_gains', return_value=gains_page) as mock_get_gains:
            result = await client.get_all_group_gains(12345, limit=50)

        self.assertEqual(len(result), 30)
        self.assertEqual(result, gains_page)
        mock_get_gains.assert_called_once_with(
            group_id=12345,
            metric=Metric.Overall,
            period=Period.Month,
            limit=50,
            offset=0,
        )

    @patch("ironforgedbot.services.wom_service.asyncio.sleep")
    async def test_get_all_group_gains_multiple_pages(self, mock_sleep):
        """Test get_all_group_gains with multiple pages."""
        # First page: full 50 items
        page1 = [SimpleNamespace(player=SimpleNamespace(username=f"Player{i}")) for i in range(1, 51)]
        # Second page: 30 items (less than limit, so end of data)
        page2 = [SimpleNamespace(player=SimpleNamespace(username=f"Player{i}")) for i in range(51, 81)]

        call_count = 0
        async def mock_get_gains(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return page1
            elif call_count == 2:
                return page2

        client = WomClient()
        with patch.object(client, 'get_group_gains', side_effect=mock_get_gains):
            result = await client.get_all_group_gains(12345, limit=50)

        self.assertEqual(len(result), 80)
        self.assertEqual(result, page1 + page2)
        mock_sleep.assert_not_called()  # No sleep for only 2 pages

    async def test_get_group_members_with_roles_success(self):
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

        client = WomClient()
        with patch.object(client, 'get_group_details', return_value=group_detail):
            valid, ignored = await client.get_group_members_with_roles(
                12345, ignored_roles=[GroupRole.Helper]
            )

        self.assertEqual(valid, ["Player1", "Player3"])
        self.assertEqual(ignored, ["Player2"])

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

        client = WomClient()
        with patch.object(client, 'get_group_details', return_value=group_detail):
            valid, ignored = await client.get_group_members_with_roles(12345)

        self.assertEqual(valid, ["Player1", "Player2"])
        self.assertEqual(ignored, [])


class TestGetWomClient(unittest.IsolatedAsyncioTestCase):
    """Test the get_wom_client function."""

    @patch('ironforgedbot.services.wom_service.CONFIG')
    async def test_get_wom_client_success(self, mock_config):
        """Test successful client creation."""
        mock_config.WOM_API_KEY = "test_key"
        mock_config.WOM_GROUP_ID = 12345

        client = await get_wom_client()

        self.assertIsInstance(client, WomClient)
        self.assertEqual(client.api_key, "test_key")
        self.assertEqual(client.group_id, 12345)

    @patch('ironforgedbot.services.wom_service.CONFIG')
    async def test_get_wom_client_missing_config(self, mock_config):
        """Test client creation with missing configuration."""
        mock_config.WOM_API_KEY = ""
        mock_config.WOM_GROUP_ID = 12345

        with self.assertRaises(WomServiceError):
            await get_wom_client()


if __name__ == "__main__":
    unittest.main()