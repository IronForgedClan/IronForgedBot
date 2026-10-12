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
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
        ) as mock_send:
            await cmd_welcome(self.interaction)

        mock_send.assert_awaited_once_with(self.interaction.user)
        self.interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        self.interaction.followup.send.assert_awaited_once_with(
            "Welcome messages sent to your DMs.", ephemeral=True
        )
        self.report_channel.send.assert_awaited_once()
        report = self.report_channel.send.await_args.args[0]
        self.assertEqual(report, "✅ Welcome messages sent to <@123> (`123`).")
        self.get_text_channel.assert_called_once_with(self.interaction.guild, 456)

    async def test_reports_dm_failure_ephemerally(self):
        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
            side_effect=discord.Forbidden(AsyncMock(), "DMs disabled"),
        ):
            await cmd_welcome(self.interaction)

        self.interaction.followup.send.assert_awaited_once_with(
            "Unable to DM welcome messages. Check that your DMs are open.",
            ephemeral=True,
        )
        self.report_channel.send.assert_awaited_once()
        report = self.report_channel.send.await_args.args[0]
        self.assertIn("❌ Unable to send welcome messages to <@123> (`123`).", report)
        self.assertIn("Reason: Forbidden:", report)
        self.assertIn("DMs disabled", report)

    async def test_reports_configuration_failure_ephemerally(self):
        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
            side_effect=ValueError("Welcome data is empty"),
        ):
            await cmd_welcome(self.interaction)

        self.interaction.followup.send.assert_awaited_once_with(
            "Unable to send welcome messages. Contact a server administrator.",
            ephemeral=True,
        )
        self.report_channel.send.assert_awaited_once()
        report = self.report_channel.send.await_args.args[0]
        self.assertEqual(
            report,
            "❌ Unable to send welcome messages to <@123> (`123`).\n"
            "Reason: ValueError: Welcome data is empty",
        )

    async def test_report_failure_does_not_block_user_confirmation(self):
        self.report_channel.send.side_effect = discord.HTTPException(
            AsyncMock(), "Report channel unavailable"
        )

        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
        ):
            await cmd_welcome(self.interaction)

        self.interaction.followup.send.assert_awaited_once()
