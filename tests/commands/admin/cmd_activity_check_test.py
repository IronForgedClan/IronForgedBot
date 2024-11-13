import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)

with patch(
    "ironforgedbot.decorators.require_role",
    mock_require_role,
):
    from ironforgedbot.commands.admin.cmd_activity_check import cmd_activity_check


class ActivityCheckTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.admin.cmd_activity_check.job_check_activity")
    @patch("ironforgedbot.commands.admin.cmd_activity_check.get_text_channel")
    async def test_cmd_activity_check(
        self, mock_get_text_channel, mock_job_check_activity
    ):
        user = create_test_member("test", ROLE.LEADERSHIP)
        mock_report_channel = Mock(discord.TextChannel)
        mock_get_text_channel.return_value = mock_report_channel
        interaction = create_mock_discord_interaction(user=user)

        await cmd_activity_check(interaction)

        interaction.followup.send.assert_called_with(
            f"Manually initiating activity check job...\nView <#{mock_report_channel.id}> for output."
        )

        mock_job_check_activity.assert_called_once()

    @patch("ironforgedbot.commands.admin.cmd_activity_check.job_check_activity")
    @patch("ironforgedbot.commands.admin.cmd_activity_check.send_error_response")
    @patch("ironforgedbot.commands.admin.cmd_activity_check.get_text_channel")
    async def test_cmd_activity_check_fails_report_channel_not_found(
        self, mock_get_text_channel, mock_send_error_reponse, mock_job_check_activity
    ):
        mock_get_text_channel.return_value = None
        interaction = create_mock_discord_interaction()

        await cmd_activity_check(interaction)

        mock_send_error_reponse.assert_called_once()
        mock_job_check_activity.assert_not_called()
