import unittest
from unittest.mock import MagicMock, Mock, patch

import discord

from ironforgedbot.tasks.membership_discrepancies import (
    job_check_membership_discrepancies,
)


class MembershipDiscrepanciesTaskTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.tasks.membership_discrepancies.logger")
    @patch("ironforgedbot.tasks.membership_discrepancies.can_start_task")
    async def test_job_check_membership_discrepancies_fails_bad_config(
        self, mock_can_start, mock_logger
    ):
        mock_can_start.return_value = None
        guild = Mock(discord.Guild)

        await job_check_membership_discrepancies(guild, "", "", 0)

        mock_logger.error.assert_called_with(
            "Bad configuration job_check_membership_discrepancies"
        )

    @patch("ironforgedbot.tasks.membership_discrepancies._send_discord_message_plain")
    @patch("ironforgedbot.tasks.membership_discrepancies._get_valid_wom_members")
    @patch("ironforgedbot.tasks.membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.membership_discrepancies.can_start_task")
    async def test_job_check_membership_discrepancies_fails_gracefully_no_users(
        self,
        mock_can_start,
        mock_get_all_discord_members,
        mock_get_valid_wom_members,
        mock_send_discord_message_plain,
    ):
        mock_can_start = MagicMock()
        mock_get_all_discord_members.return_value = []
        mock_get_valid_wom_members.return_value = None, []

        guild = Mock(discord.Guild)

        await job_check_membership_discrepancies(guild, "", "", 0)

        mock_send_discord_message_plain.assert_called_with(
            mock_can_start, "Error fetching member list, aborting."
        )
