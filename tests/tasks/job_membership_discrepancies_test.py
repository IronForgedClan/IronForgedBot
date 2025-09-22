import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import discord
import wom

from ironforgedbot.tasks.job_membership_discrepancies import (
    _get_valid_wom_members,
    job_check_membership_discrepancies,
)
from tests.helpers import create_mock_discord_guild

mock_wom_group_detail = SimpleNamespace(
    memberships=[
        SimpleNamespace(
            role=wom.GroupRole.Administrator,
            player=SimpleNamespace(username="ignored_user"),
        ),
        SimpleNamespace(
            role=wom.GroupRole.Adamant, player=SimpleNamespace(username="tester")
        ),
    ]
)


class MembershipDiscrepanciesTaskTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_guild = create_mock_discord_guild()
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_job_check_membership_basic_discrepancies(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = (["tester", "another", "foo", "bar"], [])
        mock_discord_members.return_value = ["test", "more", "foo"]

        await job_check_membership_discrepancies(
            self.mock_guild,
            self.mock_report_channel,
            self.wom_api_key,
            self.wom_group_id,
        )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call(
                "## Members Found\nDiscord: **3** members\n"
                "Wise Old Man: **4** members\n\n_Computing discrepancies..._"
            ),
            call(
                "```\nMembers found only on discord:\nmore\ntest\nMembers "
                "found only on wom:\nanother\nbar\ntester\n```"
            ),
            call(
                "## Discrepancy Summary\nDiscord Only: **2** members\n"
                "Wise Old Man Only: **3** members",
            ),
            call("Finished membership discrepancy check."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_normalizes_usernames_correctly(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = (
            [
                "tester",
                "another",
                "foo bar",
                "bar_foo",
                "foo bar",
            ],
            [],
        )
        mock_discord_members.return_value = [
            "test",
            "more",
            "foo",
            "foo-bar",
            "bar_foo",
            "foo bar",
        ]

        await job_check_membership_discrepancies(
            self.mock_guild,
            self.mock_report_channel,
            self.wom_api_key,
            self.wom_group_id,
        )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call(
                "## Members Found\nDiscord: **6** members\n"
                "Wise Old Man: **5** members\n\n_Computing discrepancies..._"
            ),
            call(
                "```\nMembers found only on discord:\nfoo\nmore\ntest\nMembers "
                "found only on wom:\nanother\ntester\n```"
            ),
            call(
                "## Discrepancy Summary\nDiscord Only: **3** members\n"
                "Wise Old Man Only: **2** members",
            ),
            call("Finished membership discrepancy check."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_ignores_case_differences(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = (
            [
                "tESter",
                "anothEr",
                "fOO-bar",
                "Bar_fOo",
                "FOO bAr",
            ],
            [],
        )
        mock_discord_members.return_value = [
            "Test",
            "More",
            "Foo",
            "Foo-Bar",
            "Bar_Foo",
            "Foo Bar",
        ]

        await job_check_membership_discrepancies(
            self.mock_guild,
            self.mock_report_channel,
            self.wom_api_key,
            self.wom_group_id,
        )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call(
                "## Members Found\nDiscord: **6** members\n"
                "Wise Old Man: **5** members\n\n_Computing discrepancies..._"
            ),
            call(
                "```\nMembers found only on discord:\nfoo\nmore\ntest\nMembers "
                "found only on wom:\nanother\ntester\n```"
            ),
            call(
                "## Discrepancy Summary\nDiscord Only: **3** members\n"
                "Wise Old Man Only: **2** members",
            ),
            call("Finished membership discrepancy check."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)

    @patch(
        "ironforgedbot.tasks.job_membership_discrepancies.IGNORED_USERS",
        ["ignored", "also_ignored"],
    )
    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_ignores_specified_users(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = (
            [
                "tester",
                "another",
                "foo",
                "bar",
            ],
            ["also_ignored"],
        )
        mock_discord_members.return_value = ["test", "more", "foo", "ignored"]

        await job_check_membership_discrepancies(
            self.mock_guild,
            self.mock_report_channel,
            self.wom_api_key,
            self.wom_group_id,
        )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call(
                "## Members Found\nDiscord: **3** members\n"
                "Wise Old Man: **4** members\n\n_Computing discrepancies..._"
            ),
            call(
                "```\nMembers found only on discord:\nmore\ntest\nMembers "
                "found only on wom:\nanother\nbar\ntester\n```"
            ),
            call(
                "## Discrepancy Summary\nDiscord Only: **2** members\n"
                "Wise Old Man Only: **3** members",
            ),
            call("Finished membership discrepancy check."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_aborts_when_no_wom_members(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = ([], [])
        mock_discord_members.return_value = ["test", "more", "foo"]

        await job_check_membership_discrepancies(
            self.mock_guild,
            self.mock_report_channel,
            self.wom_api_key,
            self.wom_group_id,
        )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call("Error computing wom member list, aborting."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_aborts_when_no_discord_members(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = (["tester", "another", "foo", "bar"], [])
        mock_discord_members.return_value = []

        await job_check_membership_discrepancies(
            self.mock_guild,
            self.mock_report_channel,
            self.wom_api_key,
            self.wom_group_id,
        )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call("Error computing discord member list, aborting."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_wom_service")
    async def test_get_valid_wom_members_success(self, mock_get_wom_service):
        mock_wom_service = AsyncMock()
        mock_wom_service.get_group_details.return_value = mock_wom_group_detail
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        members, ignored = await _get_valid_wom_members(
            self.wom_api_key, self.wom_group_id, self.mock_report_channel
        )

        self.assertEqual(members, ["tester"])
        self.assertEqual(ignored, ["ignored_user"])
        mock_wom_service.get_group_details.assert_called_once_with(self.wom_group_id)

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_wom_service")
    async def test_get_valid_wom_members_handles_wom_error(self, mock_get_wom_service):
        from ironforgedbot.services.wom_service import WomServiceError, ErrorType

        mock_wom_service = AsyncMock()
        mock_wom_service.get_group_details.side_effect = WomServiceError("API error", ErrorType.UNKNOWN)
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        members, ignored = await _get_valid_wom_members(
            self.wom_api_key, self.wom_group_id, self.mock_report_channel
        )

        self.assertEqual(members, None)
        self.assertEqual(ignored, [])
        self.mock_report_channel.send.assert_called_with(
            "Error fetching WOM group details."
        )

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_wom_service")
    async def test_get_valid_wom_members_closes_client_on_exception(self, mock_get_wom_service):
        mock_wom_service = AsyncMock()
        mock_wom_service.get_group_details.side_effect = Exception("API error")
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        members, ignored = await _get_valid_wom_members(
            self.wom_api_key, self.wom_group_id, self.mock_report_channel
        )

        self.assertEqual(members, None)
        self.assertEqual(ignored, [])
        self.mock_report_channel.send.assert_called_with("Error fetching WOM group details.")

    @patch("ironforgedbot.tasks.job_membership_discrepancies.get_all_discord_members")
    @patch("ironforgedbot.tasks.job_membership_discrepancies._get_valid_wom_members")
    async def test_handles_none_wom_members_after_filtering(
        self, mock_wom_members, mock_discord_members
    ):
        mock_wom_members.return_value = (["ignored"], [])
        mock_discord_members.return_value = ["test"]

        with patch(
            "ironforgedbot.tasks.job_membership_discrepancies.IGNORED_USERS",
            ["ignored"],
        ):
            await job_check_membership_discrepancies(
                self.mock_guild,
                self.mock_report_channel,
                self.wom_api_key,
                self.wom_group_id,
            )

        expected_calls = [
            call("Beginning membership discrepancy check..."),
            call("Error fetching member list, aborting."),
        ]

        self.assertEqual(self.mock_report_channel.send.call_args_list, expected_calls)
