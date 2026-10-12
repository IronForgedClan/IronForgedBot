import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.commands.welcome.cmd_welcome import cmd_welcome


class TestCmdWelcome(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.interaction = AsyncMock()
        self.interaction.user = Mock(id=123, mention="<@123>")
        self.report_channel = AsyncMock()
        self.get_text_channel = self.enterContext(
            patch(
                "ironforgedbot.commands.welcome.cmd_welcome.get_text_channel",
                return_value=self.report_channel,
            )
        )
        self.config = self.enterContext(
            patch("ironforgedbot.commands.welcome.cmd_welcome.CONFIG")
        )
        self.config.AUTOMATION_CHANNEL_ID = 456

    async def test_sends_welcome_and_confirms_ephemerally(self):
        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages_with_report",
            new_callable=AsyncMock,
        ) as mock_send:
            await cmd_welcome(self.interaction)

        mock_send.assert_awaited_once_with(self.interaction.user, self.report_channel)
        self.interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        self.interaction.followup.send.assert_awaited_once_with(
            "Welcome messages sent to your DMs.", ephemeral=True
        )
        self.get_text_channel.assert_called_once_with(self.interaction.guild, 456)

    async def test_reports_dm_failure_ephemerally(self):
        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages_with_report",
            new_callable=AsyncMock,
            side_effect=discord.Forbidden(AsyncMock(), "DMs disabled"),
        ) as mock_send:
            await cmd_welcome(self.interaction)

        mock_send.assert_awaited_once_with(self.interaction.user, self.report_channel)
        self.interaction.followup.send.assert_awaited_once_with(
            "Unable to DM welcome messages. Check that your DMs are open.",
            ephemeral=True,
        )

    async def test_reports_configuration_failure_ephemerally(self):
        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages_with_report",
            new_callable=AsyncMock,
            side_effect=ValueError("Welcome data is empty"),
        ) as mock_send:
            await cmd_welcome(self.interaction)

        mock_send.assert_awaited_once_with(self.interaction.user, self.report_channel)
        self.interaction.followup.send.assert_awaited_once_with(
            "Unable to send welcome messages. Contact a server administrator.",
            ephemeral=True,
        )
