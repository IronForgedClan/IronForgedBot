import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
import io

import discord
import wom
from wom import GroupRole, Metric, Period

from ironforgedbot.tasks.job_check_activity import (
    job_check_activity,
    _find_inactive_users,
    _find_wom_member,
    IRON_EXP_THRESHOLD,
    MITHRIL_EXP_THRESHOLD,
    RUNE_EXP_THRESHOLD,
    DEFAULT_WOM_LIMIT,
)


class TestJobCheckActivity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345

        self.mock_absentee = Mock()
        self.mock_absentee.nickname = "AbsentPlayer"

    @patch("ironforgedbot.tasks.job_check_activity.time")
    @patch("ironforgedbot.tasks.job_check_activity.datetime")
    @patch("ironforgedbot.tasks.job_check_activity.format_duration")
    @patch("ironforgedbot.tasks.job_check_activity.tabulate")
    @patch("ironforgedbot.tasks.job_check_activity.discord.File")
    @patch("ironforgedbot.tasks.job_check_activity._find_inactive_users")
    @patch("ironforgedbot.tasks.job_check_activity.AbsentMemberService")
    @patch("ironforgedbot.tasks.job_check_activity.db")
    async def test_job_check_activity_success(
        self,
        mock_db,
        mock_absent_service_class,
        mock_find_inactive,
        mock_discord_file,
        mock_tabulate,
        mock_format_duration,
        mock_datetime,
        mock_time,
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        mock_format_duration.return_value = "5.0s"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_absent_service = AsyncMock()
        mock_absent_service.process_absent_members.return_value = [self.mock_absentee]
        mock_absent_service_class.return_value = mock_absent_service

        mock_find_inactive.return_value = [
            ["Player1", "Iron", "100,000", "2 days ago"],
            ["Player2", "Mithril", "200,000", "5 days ago"],
        ]

        mock_tabulate.return_value = "Test table output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_check_activity(
            self.mock_report_channel, self.wom_api_key, self.wom_group_id
        )

        mock_absent_service.process_absent_members.assert_called_once()
        mock_find_inactive.assert_called_once_with(
            self.wom_api_key,
            self.wom_group_id,
            self.mock_report_channel,
            ["absentplayer"],
        )

        mock_tabulate.assert_called_once_with(
            [
                ["Player1", "Iron", "100,000", "2 days ago"],
                ["Player2", "Mithril", "200,000", "5 days ago"],
            ],
            headers=["Member", "Role", "Gained", "Last Updated"],
            tablefmt="github",
            colalign=("left", "left", "right", "right"),
        )

        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("🧗 Activity check", call_args[0][0])
        self.assertIn("Ignoring **1** absent members", call_args[0][0])
        self.assertIn("Found **2** members", call_args[0][0])
        self.assertEqual(call_args[1]["file"], mock_file)

    @patch("ironforgedbot.tasks.job_check_activity._find_inactive_users")
    @patch("ironforgedbot.tasks.job_check_activity.AbsentMemberService")
    @patch("ironforgedbot.tasks.job_check_activity.db")
    async def test_job_check_activity_empty_results(
        self, mock_db, mock_absent_service_class, mock_find_inactive
    ):
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_absent_service = AsyncMock()
        mock_absent_service.process_absent_members.return_value = []
        mock_absent_service_class.return_value = mock_absent_service

        mock_find_inactive.return_value = None

        await job_check_activity(
            self.mock_report_channel, self.wom_api_key, self.wom_group_id
        )

        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.tasks.job_check_activity.time")
    @patch("ironforgedbot.tasks.job_check_activity.datetime")
    @patch("ironforgedbot.tasks.job_check_activity.format_duration")
    @patch("ironforgedbot.tasks.job_check_activity.tabulate")
    @patch("ironforgedbot.tasks.job_check_activity.discord.File")
    @patch("ironforgedbot.tasks.job_check_activity._find_inactive_users")
    @patch("ironforgedbot.tasks.job_check_activity.AbsentMemberService")
    @patch("ironforgedbot.tasks.job_check_activity.db")
    async def test_job_check_activity_sorted_results(
        self,
        mock_db,
        mock_absent_service_class,
        mock_find_inactive,
        mock_discord_file,
        mock_tabulate,
        mock_format_duration,
        mock_datetime,
        mock_time,
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        mock_format_duration.return_value = "5.0s"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_absent_service = AsyncMock()
        mock_absent_service.process_absent_members.return_value = []
        mock_absent_service_class.return_value = mock_absent_service

        # Unsorted input - should be sorted by gained XP
        mock_find_inactive.return_value = [
            ["Player2", "Iron", "300,000", "2 days ago"],
            ["Player1", "Iron", "100,000", "1 day ago"],
            ["Player3", "Iron", "200,000", "3 days ago"],
        ]

        mock_tabulate.return_value = "Test table output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_check_activity(
            self.mock_report_channel, self.wom_api_key, self.wom_group_id
        )

        # Verify results were sorted by XP gained (lowest first)
        expected_sorted = [
            ["Player1", "Iron", "100,000", "1 day ago"],
            ["Player3", "Iron", "200,000", "3 days ago"],
            ["Player2", "Iron", "300,000", "2 days ago"],
        ]

        mock_tabulate.assert_called_once_with(
            expected_sorted,
            headers=["Member", "Role", "Gained", "Last Updated"],
            tablefmt="github",
            colalign=("left", "left", "right", "right"),
        )


class TestFindInactiveUsers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345
        self.absentees = ["absent1", "absent2"]

    @patch("ironforgedbot.tasks.job_check_activity.wom.Client")
    async def test_find_inactive_users_wom_group_error(self, mock_wom_client_class):
        mock_client = AsyncMock()
        mock_wom_client_class.return_value = mock_client

        mock_result = Mock()
        mock_result.is_ok = False
        mock_result.unwrap_err.return_value = "Group not found"
        mock_client.groups.get_details.return_value = mock_result

        result = await _find_inactive_users(
            self.wom_api_key,
            self.wom_group_id,
            self.mock_report_channel,
            self.absentees,
        )

        self.assertIsNone(result)
        mock_client.start.assert_called_once()
        mock_client.close.assert_called_once()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("Got error, fetching WOM group", call_args[1]["content"])

    @patch("ironforgedbot.tasks.job_check_activity.wom.Client")
    async def test_find_inactive_users_gains_error(self, mock_wom_client_class):
        mock_client = AsyncMock()
        mock_wom_client_class.return_value = mock_client

        # Mock successful group details
        mock_group_result = Mock()
        mock_group_result.is_ok = True
        mock_group_result.unwrap.return_value = Mock()
        mock_client.groups.get_details.return_value = mock_group_result

        # Mock failed gains request
        mock_gains_result = Mock()
        mock_gains_result.is_ok = False
        mock_gains_result.unwrap_err.return_value = "API rate limit"
        mock_client.groups.get_gains.return_value = mock_gains_result

        result = await _find_inactive_users(
            self.wom_api_key,
            self.wom_group_id,
            self.mock_report_channel,
            self.absentees,
        )

        self.assertIsNone(result)
        mock_client.close.assert_called_once()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("Got error, fetching gains from WOM", call_args[1]["content"])

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.render_relative_time")
    @patch("ironforgedbot.tasks.job_check_activity.wom.Client")
    async def test_find_inactive_users_success(
        self, mock_wom_client_class, mock_render_time, mock_find_member
    ):
        mock_client = AsyncMock()
        mock_wom_client_class.return_value = mock_client

        # Mock group details
        mock_group = Mock()
        mock_group_result = Mock()
        mock_group_result.is_ok = True
        mock_group_result.unwrap.return_value = mock_group
        mock_client.groups.get_details.return_value = mock_group_result

        # Mock member gains
        mock_player = Mock()
        mock_player.id = 123
        mock_player.username = "TestPlayer"

        mock_data = Mock()
        mock_data.gained = 50000  # Below IRON_EXP_THRESHOLD

        mock_member_gains = Mock()
        mock_member_gains.player = mock_player
        mock_member_gains.data = mock_data

        mock_gains_result = Mock()
        mock_gains_result.is_ok = True
        mock_gains_result.unwrap.return_value = [mock_member_gains]
        mock_client.groups.get_gains.return_value = mock_gains_result

        # Mock WOM member
        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Iron
        mock_wom_member.player.username = "TestPlayer"
        mock_wom_member.player.last_changed_at = datetime(2024, 1, 10)
        mock_find_member.return_value = mock_wom_member

        mock_render_time.return_value = "5 days ago"

        result = await _find_inactive_users(
            self.wom_api_key,
            self.wom_group_id,
            self.mock_report_channel,
            self.absentees,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ["TestPlayer", "Iron", "50,000", "5 days ago"])
        mock_client.close.assert_called_once()

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.wom.Client")
    async def test_find_inactive_users_skips_absentees(
        self, mock_wom_client_class, mock_find_member
    ):
        mock_client = AsyncMock()
        mock_wom_client_class.return_value = mock_client

        mock_group = Mock()
        mock_group_result = Mock()
        mock_group_result.is_ok = True
        mock_group_result.unwrap.return_value = mock_group
        mock_client.groups.get_details.return_value = mock_group_result

        # Mock player that is in absentees list
        mock_player = Mock()
        mock_player.id = 123
        mock_player.username = "absent1"  # In absentees list

        mock_data = Mock()
        mock_data.gained = 50000

        mock_member_gains = Mock()
        mock_member_gains.player = mock_player
        mock_member_gains.data = mock_data

        mock_gains_result = Mock()
        mock_gains_result.is_ok = True
        mock_gains_result.unwrap.return_value = [mock_member_gains]
        mock_client.groups.get_gains.return_value = mock_gains_result

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Iron
        mock_wom_member.player.username = "absent1"
        mock_find_member.return_value = mock_wom_member

        result = await _find_inactive_users(
            self.wom_api_key,
            self.wom_group_id,
            self.mock_report_channel,
            self.absentees,
        )

        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.wom.Client")
    async def test_find_inactive_users_skips_dogsbody(
        self, mock_wom_client_class, mock_find_member
    ):
        mock_client = AsyncMock()
        mock_wom_client_class.return_value = mock_client

        mock_group = Mock()
        mock_group_result = Mock()
        mock_group_result.is_ok = True
        mock_group_result.unwrap.return_value = mock_group
        mock_client.groups.get_details.return_value = mock_group_result

        mock_player = Mock()
        mock_player.id = 123
        mock_player.username = "TestPlayer"

        mock_data = Mock()
        mock_data.gained = 50000

        mock_member_gains = Mock()
        mock_member_gains.player = mock_player
        mock_member_gains.data = mock_data

        mock_gains_result = Mock()
        mock_gains_result.is_ok = True
        mock_gains_result.unwrap.return_value = [mock_member_gains]
        mock_client.groups.get_gains.return_value = mock_gains_result

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Dogsbody  # Should be skipped
        mock_wom_member.player.username = "TestPlayer"
        mock_find_member.return_value = mock_wom_member

        result = await _find_inactive_users(
            self.wom_api_key,
            self.wom_group_id,
            self.mock_report_channel,
            self.absentees,
        )

        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.wom.Client")
    async def test_find_inactive_users_role_mapping(
        self, mock_wom_client_class, mock_find_member
    ):
        mock_client = AsyncMock()
        mock_wom_client_class.return_value = mock_client

        mock_group = Mock()
        mock_group_result = Mock()
        mock_group_result.is_ok = True
        mock_group_result.unwrap.return_value = mock_group
        mock_client.groups.get_details.return_value = mock_group_result

        # Test different role mappings
        test_cases = [
            (GroupRole.Helper, "Alt"),
            (GroupRole.Collector, "Moderator"),
            (GroupRole.Administrator, "Admin"),
            (GroupRole.Colonel, "Staff"),
            (GroupRole.Deputy_owner, "Owner"),
            (GroupRole.Mithril, "Mithril"),  # Default case
        ]

        for wom_role, expected_role in test_cases:
            with self.subTest(wom_role=wom_role):
                mock_player = Mock()
                mock_player.id = 123
                mock_player.username = f"Player_{wom_role}"

                mock_data = Mock()
                mock_data.gained = 50000  # Below threshold

                mock_member_gains = Mock()
                mock_member_gains.player = mock_player
                mock_member_gains.data = mock_data

                mock_gains_result = Mock()
                mock_gains_result.is_ok = True
                mock_gains_result.unwrap.return_value = [mock_member_gains]
                mock_client.groups.get_gains.return_value = mock_gains_result

                mock_wom_member = Mock()
                mock_wom_member.role = wom_role
                mock_wom_member.player.username = f"Player_{wom_role}"
                mock_wom_member.player.last_changed_at = None
                mock_find_member.return_value = mock_wom_member

                result = await _find_inactive_users(
                    self.wom_api_key, self.wom_group_id, self.mock_report_channel, []
                )

                self.assertEqual(len(result), 1)
                self.assertEqual(result[0][1], expected_role)


class TestFindWomMember(unittest.TestCase):
    def test_find_wom_member_found(self):
        mock_member1 = Mock()
        mock_member1.player.id = 123

        mock_member2 = Mock()
        mock_member2.player.id = 456

        mock_group = Mock()
        mock_group.memberships = [mock_member1, mock_member2]

        result = _find_wom_member(mock_group, 456)
        self.assertEqual(result, mock_member2)

    def test_find_wom_member_not_found(self):
        mock_member1 = Mock()
        mock_member1.player.id = 123

        mock_group = Mock()
        mock_group.memberships = [mock_member1]

        result = _find_wom_member(mock_group, 999)
        self.assertIsNone(result)

    def test_find_wom_member_empty_memberships(self):
        mock_group = Mock()
        mock_group.memberships = []

        result = _find_wom_member(mock_group, 123)
        self.assertIsNone(result)


class TestThresholds(unittest.TestCase):
    def test_threshold_constants(self):
        self.assertEqual(IRON_EXP_THRESHOLD, 150_000)
        self.assertEqual(MITHRIL_EXP_THRESHOLD, 300_000)
        self.assertEqual(RUNE_EXP_THRESHOLD, 500_000)
        self.assertEqual(DEFAULT_WOM_LIMIT, 50)
