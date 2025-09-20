import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord


class TestCheckDiscrepanciesCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.check_discrepancies import cmd_check_discrepancies
        self.cmd_check_discrepancies = cmd_check_discrepancies

        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.guild = Mock()
        self.mock_interaction.response.send_message = AsyncMock()
        
        self.mock_channel = Mock()
        self.mock_channel.send = AsyncMock()

    @patch("ironforgedbot.commands.admin.check_discrepancies.job_check_membership_discrepancies")
    @patch("ironforgedbot.commands.admin.check_discrepancies.CONFIG")
    async def test_cmd_check_discrepancies_success(self, mock_config, mock_job_check):
        mock_config.WOM_API_KEY = "test_api_key"
        mock_config.WOM_GROUP_ID = "test_group_id"
        mock_job_check.return_value = None

        await self.cmd_check_discrepancies(self.mock_interaction, self.mock_channel)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating member discrepancy job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])
        
        mock_job_check.assert_called_once_with(
            self.mock_interaction.guild,
            self.mock_channel,
            "test_api_key",
            "test_group_id"
        )