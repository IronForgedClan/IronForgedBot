from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import discord
import wom

from ironforgedbot.tasks.membership_discrepancies import (
    job_check_membership_discrepancies,
    _get_valid_wom_members,
)
from tests.helpers import (
    create_mock_discord_guild,
    create_mock_wom_client,
)

mock_wom_group_detail = SimpleNamespace(
    memberships=[
        SimpleNamespace(
            **{
                "membership": SimpleNamespace(**{"role": wom.GroupRole.Administrator}),
                "player": SimpleNamespace(**{"username": "ignored_user"}),
            }
        ),
        SimpleNamespace(
            **{
                "membership": SimpleNamespace(**{"role": wom.GroupRole.Adamant}),
                "player": SimpleNamespace(**{"username": "tester"}),
            }
        ),
    ]
)


class MembershipDiscrepanciesTaskTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.tasks.membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.membership_discrepancies._get_valid_wom_members")
    async def test_job_check_membership(self, mock_wom_members, mock_discord_members):
        mock_report_channel = Mock(discord.TextChannel)
        guild = create_mock_discord_guild()

        mock_wom_members.return_value = ["tester", "another", "foo", "bar"], []
        mock_discord_members.return_value = ["test", "more", "foo"]

        await job_check_membership_discrepancies(guild, mock_report_channel, "", 0)

        expected_messages = [
            call("Beginning membership discrepancy check..."),
            call("Found **3** discord members\nFound **4** wom members..."),
            call(
                "```\nMember(s) found only on discord:\nmore\ntest\nMember(s) "
                "found only on wom:\nanother\nbar\ntester\n```"
            ),
            call(
                "Finished membership discrepancy check.\nFound **2** member(s) only "
                "on discord, and **3** member(s) only on wom."
            ),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.membership_discrepancies.IGNORED_USERS",
        ["ignored", "also_ignored"],
    )
    @patch("ironforgedbot.tasks.membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.membership_discrepancies._get_valid_wom_members")
    async def test_job_check_membership_should_ignore_users(
        self, mock_wom_members, mock_discord_members
    ):
        mock_report_channel = Mock(discord.TextChannel)
        guild = create_mock_discord_guild()

        mock_wom_members.return_value = [
            "tester",
            "another",
            "foo",
            "bar",
        ], ["also_ignored"]
        mock_discord_members.return_value = ["test", "more", "foo", "ignored"]

        await job_check_membership_discrepancies(guild, mock_report_channel, "", 0)

        expected_messages = [
            call("Beginning membership discrepancy check..."),
            call("Found **3** discord members\nFound **4** wom members..."),
            call(
                "```\nMember(s) found only on discord:\nmore\ntest\nMember(s) "
                "found only on wom:\nanother\nbar\ntester\n```"
            ),
            call(
                "Finished membership discrepancy check.\nFound **2** member(s) only "
                "on discord, and **3** member(s) only on wom."
            ),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.membership_discrepancies._get_valid_wom_members")
    async def test_job_check_membership_discrepancies_fails_no_wom_members(
        self, mock_wom_members, mock_discord_members
    ):
        mock_report_channel = Mock(discord.TextChannel)
        guild = create_mock_discord_guild()

        mock_wom_members.return_value = [], []
        mock_discord_members.return_value = ["test", "more", "foo"]

        await job_check_membership_discrepancies(guild, mock_report_channel, "", 0)

        expected_messages = [
            call("Beginning membership discrepancy check..."),
            call("Error fetching member list, aborting."),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.membership_discrepancies._get_valid_wom_members")
    async def test_job_check_membership_discrepancies_fails_no_discord_members(
        self, mock_wom_members, mock_discord_members
    ):
        mock_report_channel = Mock(discord.TextChannel)
        guild = create_mock_discord_guild()

        mock_wom_members.return_value = ["tester", "another", "foo", "bar"], []
        mock_discord_members.return_value = []

        await job_check_membership_discrepancies(guild, mock_report_channel, "", 0)

        expected_messages = [
            call("Beginning membership discrepancy check..."),
            call("Error fetching member list, aborting."),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.membership_discrepancies.Client")
    async def test_get_valid_wom_members(self, mock_wom):
        mock_report_channel = Mock(discord.TextChannel)
        mock_wom_client = AsyncMock(spec=wom.Client)
        mock_result = MagicMock()

        mock_result.is_err = False
        mock_result.unwrap.return_value = mock_wom_group_detail

        mock_wom_client.groups.get_details = AsyncMock()
        mock_wom_client.groups.get_details.return_value = mock_result

        mock_wom.return_value = mock_wom_client

        members, ignored = await _get_valid_wom_members("", 0, mock_report_channel)

        self.assertEqual(members, ["tester"])
        self.assertEqual(ignored, ["ignored_user"])

    @patch("ironforgedbot.tasks.membership_discrepancies.Client")
    async def test_get_valid_wom_members_fail_wom_error(self, mock_wom):
        mock_report_channel = Mock(discord.TextChannel)
        mock_wom_client = AsyncMock(spec=wom.Client)
        mock_result = MagicMock()

        mock_result.is_err = True
        mock_wom_client.groups.get_details = AsyncMock()

        mock_wom.return_value = mock_wom_client

        members, ignored = await _get_valid_wom_members("", 0, mock_report_channel)

        self.assertEqual(members, None)
        self.assertEqual(ignored, [])

        mock_report_channel.send.assert_called_with("Error fetching WOM group details.")
