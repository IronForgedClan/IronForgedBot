import unittest
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.commands.welcome.cmd_welcome import cmd_welcome


class TestCmdWelcome(unittest.IsolatedAsyncioTestCase):
    async def test_sends_welcome_and_confirms_ephemerally(self):
        interaction = AsyncMock()

        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
        ) as mock_send:
            await cmd_welcome(interaction)

        mock_send.assert_awaited_once_with(interaction.user)
        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once_with(
            "Welcome messages sent to your DMs.", ephemeral=True
        )

    async def test_reports_dm_failure_ephemerally(self):
        interaction = AsyncMock()

        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
            side_effect=discord.Forbidden(AsyncMock(), "DMs disabled"),
        ):
            await cmd_welcome(interaction)

        interaction.followup.send.assert_awaited_once_with(
            "Unable to DM welcome messages. Check that your DMs are open.",
            ephemeral=True,
        )

    async def test_reports_configuration_failure_ephemerally(self):
        interaction = AsyncMock()

        with patch(
            "ironforgedbot.commands.welcome.cmd_welcome.send_welcome_messages",
            new_callable=AsyncMock,
            side_effect=ValueError("Welcome data is empty"),
        ):
            await cmd_welcome(interaction)

        interaction.followup.send.assert_awaited_once_with(
            "Unable to send welcome messages. Contact a server administrator.",
            ephemeral=True,
        )
