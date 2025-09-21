import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from tests.helpers import create_mock_discord_interaction


class TestRefreshRanksCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.refresh_ranks import cmd_refresh_ranks

        self.cmd_refresh_ranks = cmd_refresh_ranks

        self.mock_interaction = create_mock_discord_interaction()
        self.mock_channel = Mock()

    @patch("ironforgedbot.commands.admin.refresh_ranks.job_refresh_ranks")
    async def test_cmd_refresh_ranks_success(self, mock_job_refresh_ranks):
        mock_job_refresh_ranks.return_value = None

        await self.cmd_refresh_ranks(self.mock_interaction, self.mock_channel)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating rank check job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])

        mock_job_refresh_ranks.assert_called_once_with(
            self.mock_interaction.guild, self.mock_channel
        )
