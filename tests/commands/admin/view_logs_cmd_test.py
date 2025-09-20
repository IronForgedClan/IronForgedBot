import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from tests.helpers import create_mock_discord_interaction


class TestViewLogsCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.view_logs import cmd_view_logs
        self.cmd_view_logs = cmd_view_logs

        self.mock_interaction = create_mock_discord_interaction()

    @patch("ironforgedbot.commands.admin.view_logs.get_latest_log_file")
    @patch("ironforgedbot.commands.admin.view_logs.send_error_response")
    async def test_cmd_view_logs_success(self, mock_send_error_response, mock_get_latest_log):
        mock_file = Mock()
        mock_get_latest_log.return_value = mock_file

        await self.cmd_view_logs(self.mock_interaction)

        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_get_latest_log.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once_with(
            content="## Latest Log File", file=mock_file
        )
        mock_send_error_response.assert_not_called()

    @patch("ironforgedbot.commands.admin.view_logs.get_latest_log_file")
    @patch("ironforgedbot.commands.admin.view_logs.send_error_response")
    async def test_cmd_view_logs_no_file(self, mock_send_error_response, mock_get_latest_log):
        mock_get_latest_log.return_value = None

        await self.cmd_view_logs(self.mock_interaction)

        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_get_latest_log.assert_called_once()
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Error processing log file."
        )
        self.mock_interaction.followup.send.assert_not_called()