import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
import io

import discord
import wom
from wom import GroupRole

from ironforgedbot.tasks.job_check_activity import (
    job_check_activity,
    _find_inactive_users,
    _find_wom_member,
    _process_member_gains,
    _get_role_display_name,
    _get_threshold_for_role,
    _sort_results_safely,
    DEFAULT_WOM_LIMIT,
)
from ironforgedbot.common.wom_role_mapping import (
    get_threshold_for_wom_role,
)
from ironforgedbot.common.roles import ROLE


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
    @patch("ironforgedbot.tasks.job_check_activity.create_absent_service")
    @patch("ironforgedbot.tasks.job_check_activity.db")
    async def test_job_check_activity_success(
        self,
        mock_db,
        mock_create_absent_service,
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
        mock_create_absent_service.return_value = mock_absent_service

        mock_find_inactive.return_value = [
            ["Player1", "Iron", "100,000", "2 days ago"],
            ["Player2", "Mithril", "200,000", "5 days ago"],
        ]

        mock_tabulate.return_value = "Test table output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_check_activity(
            self.mock_report_channel
        )

        mock_absent_service.process_absent_members.assert_called_once()
        mock_find_inactive.assert_called_once_with(
            self.mock_report_channel,
            ["absentplayer"],
            DEFAULT_WOM_LIMIT,
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

        self.assertEqual(self.mock_report_channel.send.call_count, 2)

        first_call = self.mock_report_channel.send.call_args_list[0]
        self.assertEqual(first_call[0][0], "🧗 Beginning activity check...")

        second_call = self.mock_report_channel.send.call_args_list[1]
        self.assertIn("🧗 Activity check", second_call[0][0])
        self.assertIn("Ignoring **1** absent members", second_call[0][0])
        self.assertIn("Found **2** members", second_call[0][0])
        self.assertEqual(second_call[1]["file"], mock_file)

    @patch("ironforgedbot.tasks.job_check_activity._find_inactive_users")
    @patch("ironforgedbot.tasks.job_check_activity.create_absent_service")
    @patch("ironforgedbot.tasks.job_check_activity.db")
    async def test_job_check_activity_empty_results(
        self, mock_db, mock_create_absent_service, mock_find_inactive
    ):
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_absent_service = AsyncMock()
        mock_absent_service.process_absent_members.return_value = []
        mock_create_absent_service.return_value = mock_absent_service

        mock_find_inactive.return_value = None

        await job_check_activity(
            self.mock_report_channel
        )

        # Should send beginning message and info message about no results
        self.assertEqual(self.mock_report_channel.send.call_count, 2)
        first_call = self.mock_report_channel.send.call_args_list[0]
        self.assertEqual(first_call[0][0], "🧗 Beginning activity check...")
        second_call = self.mock_report_channel.send.call_args_list[1]
        self.assertEqual(
            second_call[0][0], "ℹ️ No inactive members found meeting the criteria."
        )

    @patch("ironforgedbot.tasks.job_check_activity.time")
    @patch("ironforgedbot.tasks.job_check_activity.datetime")
    @patch("ironforgedbot.tasks.job_check_activity.format_duration")
    @patch("ironforgedbot.tasks.job_check_activity.tabulate")
    @patch("ironforgedbot.tasks.job_check_activity.discord.File")
    @patch("ironforgedbot.tasks.job_check_activity._find_inactive_users")
    @patch("ironforgedbot.tasks.job_check_activity.create_absent_service")
    @patch("ironforgedbot.tasks.job_check_activity.db")
    async def test_job_check_activity_sorted_results(
        self,
        mock_db,
        mock_create_absent_service,
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
        mock_create_absent_service.return_value = mock_absent_service

        mock_find_inactive.return_value = [
            ["Player2", "Iron", "300,000", "2 days ago"],
            ["Player1", "Iron", "100,000", "1 day ago"],
            ["Player3", "Iron", "200,000", "3 days ago"],
        ]

        mock_tabulate.return_value = "Test table output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_check_activity(
            self.mock_report_channel
        )

        self.assertEqual(self.mock_report_channel.send.call_count, 2)

        first_call = self.mock_report_channel.send.call_args_list[0]
        self.assertEqual(first_call[0][0], "🧗 Beginning activity check...")

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

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_wom_group_error(self, mock_get_wom_client):
        from ironforgedbot.services.wom_service import WomServiceError

        mock_wom_service = AsyncMock()
        mock_wom_service.get_group_details.side_effect = WomServiceError("Group not found")
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        mock_wom_service.get_group_details.assert_called_once_with()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API is currently unavailable", call_args.args[0])

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_gains_error(self, mock_get_wom_client):
        from ironforgedbot.services.wom_service import WomServiceError

        mock_wom_service = AsyncMock()
        mock_group_detail = Mock()
        mock_wom_service.get_group_details.return_value = mock_group_detail
        mock_wom_service.get_all_group_gains.side_effect = WomServiceError("API rate limit")
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        mock_wom_service.get_group_details.assert_called_once_with()
        mock_wom_service.get_all_group_gains.assert_called_once()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API rate limit exceeded", call_args.args[0])

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.render_relative_time")
    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_success(
        self, mock_get_wom_client, mock_render_time, mock_find_member
    ):
        mock_wom_service = AsyncMock()
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        mock_group = Mock()
        mock_wom_service.get_group_details.return_value = mock_group

        mock_player = Mock()
        mock_player.id = 123
        mock_player.username = "TestPlayer"

        mock_data = Mock()
        mock_data.gained = (
            50000  # Below member threshold which is 150,000
        )

        mock_member_gains = Mock()
        mock_member_gains.player = mock_player
        mock_member_gains.data = mock_data

        mock_wom_service.get_all_group_gains.return_value = [mock_member_gains]

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Iron
        mock_wom_member.player.username = "TestPlayer"
        mock_wom_member.player.last_changed_at = datetime(2024, 1, 10)
        mock_find_member.return_value = mock_wom_member

        mock_render_time.return_value = "5 days ago"

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ["TestPlayer", "Member", "50,000", "5 days ago"])
        mock_wom_service.get_group_details.assert_called_once_with()
        mock_wom_service.get_all_group_gains.assert_called_once()

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_skips_absentees(
        self, mock_get_wom_client, mock_find_member
    ):
        mock_wom_service = AsyncMock()
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        mock_group = Mock()
        mock_wom_service.get_group_details.return_value = mock_group

        mock_player = Mock()
        mock_player.id = 123
        mock_player.username = "absent1"  # In absentees list

        mock_data = Mock()
        mock_data.gained = 50000

        mock_member_gains = Mock()
        mock_member_gains.player = mock_player
        mock_member_gains.data = mock_data

        mock_wom_service.get_all_group_gains.return_value = [mock_member_gains]

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Iron
        mock_wom_member.player.username = "absent1"
        mock_find_member.return_value = mock_wom_member

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_skips_dogsbody(
        self, mock_get_wom_client, mock_find_member
    ):
        mock_wom_service = AsyncMock()
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        mock_group = Mock()
        mock_wom_service.get_group_details.return_value = mock_group

        mock_player = Mock()
        mock_player.id = 123
        mock_player.username = "TestPlayer"

        mock_data = Mock()
        mock_data.gained = 50000

        mock_member_gains = Mock()
        mock_member_gains.player = mock_player
        mock_member_gains.data = mock_data

        mock_wom_service.get_all_group_gains.return_value = [mock_member_gains]

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Dogsbody  # Should be skipped
        mock_wom_member.player.username = "TestPlayer"
        mock_find_member.return_value = mock_wom_member

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_role_mapping(
        self, mock_get_wom_client, mock_find_member
    ):
        mock_wom_service = AsyncMock()
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        mock_group = Mock()
        mock_wom_service.get_group_details.return_value = mock_group

        test_cases = [
            (GroupRole.Helper, "Staff"),           # Maps to ROLE.STAFF
            (GroupRole.Collector, "Staff"),       # Maps to ROLE.STAFF
            (GroupRole.Administrator, "Leadership"),  # Maps to ROLE.LEADERSHIP
            (GroupRole.Colonel, "Staff"),       # Maps to ROLE.STAFF
            (GroupRole.Deputy_owner, "Leadership"),  # Maps to ROLE.LEADERSHIP
            (GroupRole.Mithril, "Member"),          # Maps to ROLE.MEMBER
        ]

        for wom_role, expected_role in test_cases:
            with self.subTest(wom_role=wom_role):
                mock_player = Mock()
                mock_player.id = 123
                mock_player.username = f"Player_{wom_role}"

                mock_data = Mock()
                mock_data.gained = 50000  # Below any threshold

                mock_member_gains = Mock()
                mock_member_gains.player = mock_player
                mock_member_gains.data = mock_data

                mock_gains_result = Mock()
                mock_gains_result.is_ok = True
                mock_gains_result.unwrap.return_value = [mock_member_gains]
                mock_wom_service.get_all_group_gains.return_value = [mock_member_gains]

                mock_wom_member = Mock()
                mock_wom_member.role = wom_role
                mock_wom_member.player.username = f"Player_{wom_role}"
                mock_wom_member.player.last_changed_at = None
                mock_find_member.return_value = mock_wom_member

                result = await _find_inactive_users(
                    self.mock_report_channel,
                    [],
                    DEFAULT_WOM_LIMIT,
                        )

                # Staff and Leadership roles should be exempt from activity checks
                if expected_role in ["Staff", "Leadership"]:
                    self.assertEqual(len(result), 0, f"{wom_role} should be exempt from activity checks")
                else:
                    self.assertEqual(len(result), 1, f"{wom_role} should be subject to activity checks")
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


class TestValidationAndHelpers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345

    def test_get_role_display_name(self):
        """Test role display name mapping"""
        self.assertEqual(_get_role_display_name(GroupRole.Helper), "Staff")
        self.assertEqual(_get_role_display_name(GroupRole.Collector), "Staff")
        self.assertEqual(_get_role_display_name(GroupRole.Administrator), "Leadership")
        self.assertEqual(_get_role_display_name(GroupRole.Colonel), "Staff")
        self.assertEqual(_get_role_display_name(GroupRole.Deputy_owner), "Leadership")
        self.assertEqual(_get_role_display_name(GroupRole.Iron), "Member")
        self.assertEqual(_get_role_display_name(None), "Unknown")

    def test_get_threshold_for_role(self):
        """Test threshold calculation for roles"""
        # Test that the new system uses rank-based thresholds
        # GroupRole.Iron maps to RANK.IRON (150k threshold)
        self.assertEqual(_get_threshold_for_role(GroupRole.Iron), 150_000)
        # GroupRole.Mithril maps to RANK.MITHRIL (150k threshold)
        self.assertEqual(_get_threshold_for_role(GroupRole.Mithril), 150_000)

        # Test that None returns max threshold (GOD rank)
        # Should be 500k for GOD rank
        self.assertEqual(_get_threshold_for_role(None), 500_000)

    def test_sort_results_safely(self):
        """Test safe sorting with malformed data"""
        results = [
            ["Player1", "Iron", "300,000", "1 day"],
            ["Player2", "Iron", "100,000", "2 days"],
            ["Player3", "Iron", "invalid", "3 days"],  # Malformed XP
            ["Player4", "Iron", "200,000", "4 days"],
        ]

        sorted_results = _sort_results_safely(results)

        # Should sort by XP, with malformed data (0) first
        self.assertEqual(sorted_results[0][0], "Player3")  # 0 (malformed)
        self.assertEqual(sorted_results[1][0], "Player2")  # 100,000
        self.assertEqual(sorted_results[2][0], "Player4")  # 200,000
        self.assertEqual(sorted_results[3][0], "Player1")  # 300,000

    def test_sort_results_safely_empty_list(self):
        """Test safe sorting with empty list"""
        self.assertEqual(_sort_results_safely([]), [])

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    @patch("ironforgedbot.tasks.job_check_activity.render_relative_time")
    def test_process_member_gains_inactive_member(
        self, mock_render_time, mock_find_member
    ):
        """Test processing of inactive member"""
        mock_member_gains = Mock()
        mock_member_gains.player.id = 123
        mock_member_gains.player.username = "TestPlayer"
        mock_member_gains.data.gained = 50000

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Iron
        mock_wom_member.player.username = "TestPlayer"
        mock_wom_member.player.last_changed_at = datetime(2024, 1, 10)
        mock_find_member.return_value = mock_wom_member

        mock_render_time.return_value = "5 days ago"
        mock_group = Mock()

        result = _process_member_gains(
            mock_member_gains, mock_group, []
        )

        self.assertEqual(result, ["TestPlayer", "Member", "50,000", "5 days ago"])

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    def test_process_member_gains_active_member(self, mock_find_member):
        """Test processing of active member (above threshold)"""
        mock_member_gains = Mock()
        mock_member_gains.player.id = 123
        mock_member_gains.data.gained = 200000  # Above Iron threshold

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Iron
        mock_find_member.return_value = mock_wom_member

        mock_group = Mock()

        result = _process_member_gains(
            mock_member_gains, mock_group, []
        )

        self.assertIsNone(result)  # Should return None for active members

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    def test_process_member_gains_absentee(self, mock_find_member):
        """Test processing of absent member"""
        mock_member_gains = Mock()
        mock_member_gains.player.id = 123

        mock_wom_member = Mock()
        mock_wom_member.player.username = "AbsentPlayer"
        mock_find_member.return_value = mock_wom_member

        mock_group = Mock()
        absentees = ["absentplayer"]  # lowercase

        result = _process_member_gains(
            mock_member_gains, mock_group, absentees
        )

        self.assertIsNone(result)  # Should return None for absent members

    @patch("ironforgedbot.tasks.job_check_activity._find_wom_member")
    def test_process_member_gains_dogsbody(self, mock_find_member):
        """Test processing of dogsbody member"""
        mock_member_gains = Mock()
        mock_member_gains.player.id = 123

        mock_wom_member = Mock()
        mock_wom_member.role = GroupRole.Dogsbody
        mock_find_member.return_value = mock_wom_member

        mock_group = Mock()

        result = _process_member_gains(
            mock_member_gains, mock_group, []
        )

        self.assertIsNone(result)  # Should return None for dogsbody members

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_json_decode_error(self, mock_get_wom_client):
        """Test handling of JSON decode errors from WOM API"""
        mock_wom_service = AsyncMock()
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        # Mock JSON decode error when fetching group details
        from ironforgedbot.services.wom_service import WomServiceError
        json_error = WomServiceError("JSON is malformed: invalid character (byte 0)")
        mock_wom_service.get_group_details.side_effect = json_error

        result = await _find_inactive_users(
            self.mock_report_channel,
            [],
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API is currently unavailable", call_args[0][0])

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_client")
    async def test_find_inactive_users_json_decode_error_in_gains(
        self, mock_get_wom_client
    ):
        """Test handling of JSON decode errors when fetching gains"""
        mock_wom_service = AsyncMock()
        mock_get_wom_client.return_value.__aenter__.return_value = mock_wom_service

        # Mock successful group details
        mock_group = Mock()
        mock_wom_service.get_group_details.return_value = mock_group

        # Mock JSON decode error when fetching gains
        from ironforgedbot.services.wom_service import WomServiceError
        json_error = WomServiceError("JSON is malformed: invalid character (byte 0)")
        mock_wom_service.get_all_group_gains.side_effect = json_error

        result = await _find_inactive_users(
            self.mock_report_channel,
            [],
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API error occurred", call_args[0][0])


class TestThresholds(unittest.TestCase):
    def test_threshold_constants(self):
        """Test default threshold values"""
        # Test that default constants are available
        self.assertEqual(DEFAULT_WOM_LIMIT, 50)

    def test_wom_role_thresholds(self):
        """Test WOM role threshold mapping"""
        # Test that WOM roles map correctly to rank-based thresholds
        # GroupRole.Iron maps to RANK.IRON (150k threshold)
        self.assertEqual(get_threshold_for_wom_role(GroupRole.Iron), 150_000)
        # GroupRole.Mithril maps to RANK.MITHRIL (150k threshold)
        self.assertEqual(get_threshold_for_wom_role(GroupRole.Mithril), 150_000)
        # GroupRole.Adamant maps to RANK.ADAMANT (200k threshold)
        self.assertEqual(get_threshold_for_wom_role(GroupRole.Adamant), 200_000)
        # GroupRole.Helper has no rank mapping, should get GOD threshold (500k)
        self.assertEqual(get_threshold_for_wom_role(GroupRole.Helper), 500_000)
        # GroupRole.Administrator has no rank mapping, should get GOD threshold (500k)
        self.assertEqual(get_threshold_for_wom_role(GroupRole.Administrator), 500_000)

    def test_role_display_mapping(self):
        """Test role display mapping using new system"""
        # Test that role display names work correctly
        self.assertEqual(_get_role_display_name(GroupRole.Helper), "Staff")
        self.assertEqual(_get_role_display_name(GroupRole.Collector), "Staff")
        self.assertEqual(_get_role_display_name(GroupRole.Administrator), "Leadership")
        self.assertEqual(_get_role_display_name(GroupRole.Iron), "Member")
        self.assertEqual(_get_role_display_name(None), "Unknown")
