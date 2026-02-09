import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone
import io

import discord
import wom
from wom import GroupRole

from ironforgedbot.tasks.job_check_activity import (
    job_check_activity,
    _find_inactive_users,
    _sort_results_safely,
    DEFAULT_WOM_LIMIT,
)
from ironforgedbot.common.activity_check import ActivityCheckResult
from ironforgedbot.common.roles import ROLE


def create_mock_activity_result(
    username="TestPlayer",
    wom_role=GroupRole.Iron,
    discord_role="Member",
    xp_gained=50000,
    xp_threshold=150000,
    is_active=False,
    is_exempt=False,
    is_absent=False,
    is_prospect=False,
    last_changed_at=None,
    skip_reason=None,
):
    """Helper to create ActivityCheckResult for testing."""
    return ActivityCheckResult(
        username=username,
        wom_role=wom_role,
        discord_role=discord_role,
        xp_gained=xp_gained,
        xp_threshold=xp_threshold,
        is_active=is_active,
        is_exempt=is_exempt,
        is_absent=is_absent,
        is_prospect=is_prospect,
        last_changed_at=last_changed_at,
        check_timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        skip_reason=skip_reason,
    )


class TestJobCheckActivity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345

        self.mock_absentee = Mock()
        self.mock_absentee.nickname = "AbsentPlayer"

    @patch("ironforgedbot.tasks.job_check_activity.time.perf_counter", side_effect=[0.0, 5.0])
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
        mock_perf_counter,
    ):
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        mock_format_duration.return_value = "5.0s"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_absent_service = AsyncMock()
        mock_absent_service.process_absent_members.return_value = [self.mock_absentee]
        mock_create_absent_service.return_value = mock_absent_service

        # Return ActivityCheckResult objects
        mock_find_inactive.return_value = [
            create_mock_activity_result(
                username="Player1",
                discord_role="Member",
                xp_gained=100000,
                xp_threshold=150000,
                is_active=False,
                last_changed_at=datetime(2024, 1, 13, 10, 30, 0, tzinfo=timezone.utc),
            ),
            create_mock_activity_result(
                username="Player2",
                discord_role="Member",
                xp_gained=200000,
                xp_threshold=150000,
                is_active=False,
                last_changed_at=datetime(2024, 1, 10, 10, 30, 0, tzinfo=timezone.utc),
            ),
        ]

        mock_tabulate.return_value = "Test table output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_check_activity(self.mock_report_channel)

        mock_absent_service.process_absent_members.assert_called_once()
        mock_find_inactive.assert_called_once_with(
            self.mock_report_channel,
            ["absentplayer"],
            DEFAULT_WOM_LIMIT,
        )

        # Verify tabulate was called with formatted data
        self.assertTrue(mock_tabulate.called)
        call_args = mock_tabulate.call_args[0][0]
        self.assertEqual(len(call_args), 2)
        self.assertEqual(call_args[0][0], "Player1")
        self.assertEqual(call_args[1][0], "Player2")

        self.assertEqual(self.mock_report_channel.send.call_count, 2)

        first_call = self.mock_report_channel.send.call_args_list[0]
        self.assertEqual(first_call[0][0], "🧗 **Activity Check:** starting...")

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

        await job_check_activity(self.mock_report_channel)

        # Should send beginning message and info message about no results
        self.assertEqual(self.mock_report_channel.send.call_count, 2)
        first_call = self.mock_report_channel.send.call_args_list[0]
        self.assertEqual(first_call[0][0], "🧗 **Activity Check:** starting...")
        second_call = self.mock_report_channel.send.call_args_list[1]
        self.assertEqual(
            second_call[0][0], "ℹ️ No inactive members found meeting the criteria."
        )

    @patch("ironforgedbot.tasks.job_check_activity.time.perf_counter", side_effect=[0.0, 5.0])
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
        mock_perf_counter,
    ):
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 30, 0)
        mock_format_duration.return_value = "5.0s"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_absent_service = AsyncMock()
        mock_absent_service.process_absent_members.return_value = []
        mock_create_absent_service.return_value = mock_absent_service

        # Return ActivityCheckResult objects
        mock_find_inactive.return_value = [
            create_mock_activity_result(
                username="Player2",
                discord_role="Member",
                xp_gained=300000,
                xp_threshold=150000,
                is_active=False,
                last_changed_at=datetime(2024, 1, 13, 10, 30, 0, tzinfo=timezone.utc),
            ),
            create_mock_activity_result(
                username="Player1",
                discord_role="Member",
                xp_gained=100000,
                xp_threshold=150000,
                is_active=False,
                last_changed_at=datetime(2024, 1, 14, 10, 30, 0, tzinfo=timezone.utc),
            ),
            create_mock_activity_result(
                username="Player3",
                discord_role="Member",
                xp_gained=200000,
                xp_threshold=150000,
                is_active=False,
                last_changed_at=datetime(2024, 1, 12, 10, 30, 0, tzinfo=timezone.utc),
            ),
        ]

        mock_tabulate.return_value = "Test table output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_check_activity(self.mock_report_channel)

        self.assertEqual(self.mock_report_channel.send.call_count, 2)

        first_call = self.mock_report_channel.send.call_args_list[0]
        self.assertEqual(first_call[0][0], "🧗 **Activity Check:** starting...")

        # Verify results are sorted by XP gained (lowest to highest)
        self.assertTrue(mock_tabulate.called)
        call_args = mock_tabulate.call_args[0][0]
        self.assertEqual(len(call_args), 3)
        # Should be sorted by XP: Player1 (100k), Player3 (200k), Player2 (300k)
        self.assertEqual(call_args[0][0], "Player1")
        self.assertEqual(call_args[1][0], "Player3")
        self.assertEqual(call_args[2][0], "Player2")


class TestFindInactiveUsers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345
        self.absentees = ["absent1", "absent2"]

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_service")
    async def test_find_inactive_users_wom_group_error(self, mock_get_wom_service):
        from ironforgedbot.services.wom_service import WomServiceError

        mock_wom_service = AsyncMock()
        mock_wom_service.get_monthly_activity_data.side_effect = WomServiceError(
            "Group not found"
        )
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        mock_wom_service.get_monthly_activity_data.assert_called_once()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API is currently unavailable", call_args.args[0])

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_service")
    async def test_find_inactive_users_gains_error(self, mock_get_wom_service):
        from ironforgedbot.services.wom_service import WomRateLimitError

        mock_wom_service = AsyncMock()
        mock_wom_service.get_monthly_activity_data.side_effect = WomRateLimitError(
            "API rate limit"
        )
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        result = await _find_inactive_users(
            self.mock_report_channel,
            self.absentees,
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        mock_wom_service.get_monthly_activity_data.assert_called_once()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API rate limit exceeded", call_args.args[0])


class TestValidationAndHelpers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.wom_api_key = "test_api_key"
        self.wom_group_id = 12345

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

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_service")
    async def test_find_inactive_users_json_decode_error(self, mock_get_wom_service):
        """Test handling of JSON decode errors from WOM API"""
        mock_wom_service = AsyncMock()
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        # Mock JSON decode error when fetching group details
        from ironforgedbot.services.wom_service import WomServiceError

        json_error = WomServiceError("JSON is malformed: invalid character (byte 0)")
        mock_wom_service.get_monthly_activity_data.side_effect = json_error

        result = await _find_inactive_users(
            self.mock_report_channel,
            [],
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API is currently unavailable", call_args[0][0])

    @patch("ironforgedbot.tasks.job_check_activity.get_wom_service")
    async def test_find_inactive_users_json_decode_error_in_gains(
        self, mock_get_wom_service
    ):
        """Test handling of JSON decode errors when fetching gains"""
        mock_wom_service = AsyncMock()
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        # Mock JSON decode error when fetching activity data
        from ironforgedbot.services.wom_service import WomServiceError

        json_error = WomServiceError("JSON is malformed: invalid character (byte 0)")
        mock_wom_service.get_monthly_activity_data.side_effect = json_error

        result = await _find_inactive_users(
            self.mock_report_channel,
            [],
            DEFAULT_WOM_LIMIT,
        )

        self.assertIsNone(result)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args
        self.assertIn("WOM API is currently unavailable", call_args[0][0])


class TestThresholds(unittest.TestCase):
    def test_threshold_constants(self):
        """Test default threshold values"""
        # Test that default constants are available
        self.assertEqual(DEFAULT_WOM_LIMIT, 50)
