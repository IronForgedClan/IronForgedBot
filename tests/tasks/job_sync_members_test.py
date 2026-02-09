import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone
import io

import discord

from ironforgedbot.tasks.job_sync_members import job_sync_members


class TestJobSyncMembers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()

    @patch("ironforgedbot.tasks.job_sync_members.time.perf_counter", side_effect=[0.0, 5.0])
    @patch("ironforgedbot.tasks.job_sync_members.sync_members")
    async def test_job_sync_members_no_changes(self, mock_sync_members, mock_perf_counter):
        mock_sync_members.return_value = []

        await job_sync_members(self.mock_guild, self.mock_report_channel)

        mock_sync_members.assert_called_once_with(self.mock_guild)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("No changes", call_args)
        self.assertIn("🔁 **Member Sync**", call_args)

    @patch("ironforgedbot.tasks.job_sync_members.time.perf_counter", side_effect=[0.0, 5.0])
    @patch("ironforgedbot.tasks.job_sync_members.datetime")
    @patch("ironforgedbot.tasks.job_sync_members.text_h2")
    @patch("ironforgedbot.tasks.job_sync_members.datetime_to_discord_relative")
    @patch("ironforgedbot.tasks.job_sync_members.format_duration")
    @patch("ironforgedbot.tasks.job_sync_members.tabulate")
    @patch("ironforgedbot.tasks.job_sync_members.discord.File")
    @patch("ironforgedbot.tasks.job_sync_members.sync_members")
    async def test_job_sync_members_with_changes(
        self,
        mock_sync_members,
        mock_discord_file,
        mock_tabulate,
        mock_format_duration,
        mock_datetime_relative,
        mock_text_h2,
        mock_datetime,
        mock_perf_counter,
    ):
        mock_datetime.now.return_value = datetime(
            2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc
        )
        mock_sync_members.return_value = [
            ["Player1", "Added", "New member"],
            ["Player2", "Updated", "Role change"],
        ]
        mock_tabulate.return_value = "Member\tAction\tReason\nPlayer1\tAdded\tNew member\nPlayer2\tUpdated\tRole change"
        mock_format_duration.return_value = "5.0s"
        mock_datetime_relative.return_value = "<t:1705314600:t>"
        mock_text_h2.return_value = "## 🔁 Member Synchronization"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_sync_members(self.mock_guild, self.mock_report_channel)

        mock_sync_members.assert_called_once_with(self.mock_guild)
        mock_tabulate.assert_called_once_with(
            [["Player1", "Added", "New member"], ["Player2", "Updated", "Role change"]],
            headers=["Member", "Action", "Reason"],
            tablefmt="simple",
        )
        mock_discord_file.assert_called_once()

        file_call_args = mock_discord_file.call_args
        self.assertIsInstance(file_call_args[1]["fp"], io.BytesIO)
        self.assertTrue(file_call_args[1]["filename"].startswith("sync_results_"))
        self.assertTrue(file_call_args[1]["filename"].endswith(".txt"))

        self.mock_report_channel.send.assert_called_once()
        send_call_args = self.mock_report_channel.send.call_args
        self.assertIn("Member Synchronization", send_call_args[0][0])
        self.assertEqual(send_call_args[1]["file"], mock_file)

    @patch("ironforgedbot.tasks.job_sync_members.time.perf_counter", side_effect=[0.0, 5.0])
    @patch("ironforgedbot.tasks.job_sync_members.sync_members")
    async def test_job_sync_members_handles_exception(
        self, mock_sync_members, mock_perf_counter
    ):
        mock_sync_members.side_effect = Exception("Database error")

        await job_sync_members(self.mock_guild, self.mock_report_channel)

        mock_sync_members.assert_called_once_with(self.mock_guild)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("🚨 An unhandled error occurred during member sync", call_args)
        self.assertIn("Please check the logs", call_args)

    @patch("ironforgedbot.tasks.job_sync_members.time.perf_counter", side_effect=[0.0, 2.5])
    @patch("ironforgedbot.tasks.job_sync_members.datetime")
    @patch("ironforgedbot.tasks.job_sync_members.text_h2")
    @patch("ironforgedbot.tasks.job_sync_members.datetime_to_discord_relative")
    @patch("ironforgedbot.tasks.job_sync_members.format_duration")
    @patch("ironforgedbot.tasks.job_sync_members.tabulate")
    @patch("ironforgedbot.tasks.job_sync_members.discord.File")
    @patch("ironforgedbot.tasks.job_sync_members.sync_members")
    async def test_job_sync_members_file_creation(
        self,
        mock_sync_members,
        mock_discord_file,
        mock_tabulate,
        mock_format_duration,
        mock_datetime_relative,
        mock_text_h2,
        mock_datetime,
        mock_perf_counter,
    ):
        mock_datetime.now.side_effect = [
            datetime(
                2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc
            ),  # First call for 'now'
            datetime(
                2024, 1, 15, 10, 30, 5, tzinfo=timezone.utc
            ),  # Second call for filename
        ]
        mock_sync_members.return_value = [["TestPlayer", "Removed", "Left guild"]]
        mock_tabulate.return_value = "Test table output"
        mock_format_duration.return_value = "2.5s"
        mock_datetime_relative.return_value = "<t:1705314600:t>"
        mock_text_h2.return_value = "## 🔁 Member Synchronization"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_sync_members(self.mock_guild, self.mock_report_channel)

        mock_discord_file.assert_called_once()
        file_call = mock_discord_file.call_args

        # Check that the BytesIO contains the tabulated data
        fp = file_call[1]["fp"]
        self.assertIsInstance(fp, io.BytesIO)
        fp.seek(0)
        content = fp.read().decode("utf-8")
        self.assertEqual(content, "Test table output")

        # Check filename format
        filename = file_call[1]["filename"]
        self.assertTrue(filename.startswith("sync_results_"))
        self.assertTrue(filename.endswith(".txt"))
        self.assertIn("20240115_103005", filename)

    @patch("ironforgedbot.tasks.job_sync_members.time.perf_counter", side_effect=[0.0, 1.0])
    @patch("ironforgedbot.tasks.job_sync_members.sync_members")
    async def test_job_sync_members_empty_changes_list(
        self, mock_sync_members, mock_perf_counter
    ):
        mock_sync_members.return_value = []

        await job_sync_members(self.mock_guild, self.mock_report_channel)

        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("No changes", call_args)
        self.assertNotIn("file=", str(self.mock_report_channel.send.call_args))

    @patch("ironforgedbot.tasks.job_sync_members.time.perf_counter", side_effect=[0.0, 10.0])
    @patch("ironforgedbot.tasks.job_sync_members.datetime")
    @patch("ironforgedbot.tasks.job_sync_members.text_h2")
    @patch("ironforgedbot.tasks.job_sync_members.datetime_to_discord_relative")
    @patch("ironforgedbot.tasks.job_sync_members.format_duration")
    @patch("ironforgedbot.tasks.job_sync_members.tabulate")
    @patch("ironforgedbot.tasks.job_sync_members.discord.File")
    @patch("ironforgedbot.tasks.job_sync_members.sync_members")
    async def test_job_sync_members_multiple_changes(
        self,
        mock_sync_members,
        mock_discord_file,
        mock_tabulate,
        mock_format_duration,
        mock_datetime_relative,
        mock_text_h2,
        mock_datetime,
        mock_perf_counter,
    ):
        mock_datetime.now.return_value = datetime(
            2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc
        )
        mock_sync_members.return_value = [
            ["Player1", "Added", "New guild member"],
            ["Player2", "Updated", "Nickname change"],
            ["Player3", "Removed", "Left guild"],
            ["Player4", "Updated", "Rank promotion"],
        ]
        mock_tabulate.return_value = "Multiple changes table"
        mock_format_duration.return_value = "10.0s"
        mock_datetime_relative.return_value = "<t:1705314600:t>"
        mock_text_h2.return_value = "## 🔁 Member Synchronization"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await job_sync_members(self.mock_guild, self.mock_report_channel)

        mock_tabulate.assert_called_once_with(
            [
                ["Player1", "Added", "New guild member"],
                ["Player2", "Updated", "Nickname change"],
                ["Player3", "Removed", "Left guild"],
                ["Player4", "Updated", "Rank promotion"],
            ],
            headers=["Member", "Action", "Reason"],
            tablefmt="simple",
        )

        self.mock_report_channel.send.assert_called_once()
        send_call_args = self.mock_report_channel.send.call_args
        self.assertEqual(send_call_args[1]["file"], mock_file)
