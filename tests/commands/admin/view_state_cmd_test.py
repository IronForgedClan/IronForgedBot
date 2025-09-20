import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord


class TestViewStateCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.view_state import cmd_view_state
        self.cmd_view_state = cmd_view_state

        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.response.defer = AsyncMock()
        self.mock_interaction.followup.send = AsyncMock()

    @patch("ironforgedbot.commands.admin.view_state.get_internal_state")
    async def test_cmd_view_state_success(self, mock_get_internal_state):
        mock_file = Mock()
        mock_get_internal_state.return_value = mock_file

        await self.cmd_view_state(self.mock_interaction)

        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_get_internal_state.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once_with(
            content="## Current Internal State", file=mock_file
        )