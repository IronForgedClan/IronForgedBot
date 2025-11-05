import unittest
from unittest.mock import AsyncMock

from ironforgedbot.decorators.require_channel import require_channel
from tests.helpers import create_mock_discord_interaction


class TestRequireChannelDecorator(unittest.IsolatedAsyncioTestCase):
    def create_channel_test_setup(self, channel_id=555, allowed_channels=None):
        """Helper to create standardized test setup for channel decorator tests."""
        if allowed_channels is None:
            allowed_channels = [channel_id, 12345, 54321]

        mock_func = AsyncMock()
        mock_interaction = create_mock_discord_interaction(channel_id=channel_id)

        return mock_func, mock_interaction, allowed_channels

    async def test_require_channel_with_valid_channel(self):
        """Test that decorator works when in allowed channel"""
        mock_func, mock_interaction, allowed_channels = self.create_channel_test_setup()

        decorated_func = require_channel(allowed_channels)(mock_func)

        self.assertIn(mock_interaction.channel_id, allowed_channels)

    async def test_require_channel_with_empty_channel_list(self):
        """Test that empty channel list blocks all channels"""
        mock_func = AsyncMock()
        mock_interaction = create_mock_discord_interaction(channel_id=555)
        mock_interaction.response.is_done.return_value = False
        decorated_func = require_channel([])(mock_func)

        result = await decorated_func(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        self.assertIsNone(result)

    async def test_require_channel_sends_error_for_invalid_channel(self):
        """Test that error is sent for wrong channel"""
        mock_func, mock_interaction, _ = self.create_channel_test_setup(
            channel_id=999, allowed_channels=[12345, 54321]
        )
        mock_interaction.response.is_done.return_value = False

        decorated_func = require_channel([12345, 54321])(mock_func)
        result = await decorated_func(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        self.assertTrue(call_args.kwargs.get("ephemeral", False))
        mock_func.assert_not_called()
