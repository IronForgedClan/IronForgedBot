import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from tests.helpers import create_mock_discord_interaction


class TestCheckActivityCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.check_activity import cmd_check_activity

        self.cmd_check_activity = cmd_check_activity

        self.mock_interaction = create_mock_discord_interaction()
        self.mock_channel = Mock()

    @patch("ironforgedbot.commands.admin.check_activity.job_check_activity")
    @patch("ironforgedbot.commands.admin.check_activity.CONFIG")
    async def test_cmd_check_activity_success(
        self, mock_config, mock_job_check_activity
    ):
        mock_config.WOM_API_KEY = "test_api_key"
        mock_config.WOM_GROUP_ID = "test_group_id"
        mock_job_check_activity.return_value = None

        await self.cmd_check_activity(self.mock_interaction, self.mock_channel)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating activity check job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])

        mock_job_check_activity.assert_called_once_with(
            self.mock_channel
        )
