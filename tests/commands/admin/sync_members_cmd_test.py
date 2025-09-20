import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord


class TestSyncMembersCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.sync_members import cmd_sync_members
        self.cmd_sync_members = cmd_sync_members

        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.guild = Mock()
        self.mock_interaction.response.send_message = AsyncMock()
        
        self.mock_channel = Mock()

    @patch("ironforgedbot.tasks.job_sync_members.job_sync_members")
    async def test_cmd_sync_members_success(self, mock_job_sync_members):
        mock_job_sync_members.return_value = None

        await self.cmd_sync_members(self.mock_interaction, self.mock_channel)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating member sync job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])
        
        mock_job_sync_members.assert_called_once_with(
            self.mock_interaction.guild, self.mock_channel
        )