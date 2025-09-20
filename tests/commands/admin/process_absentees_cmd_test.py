import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from tests.helpers import create_mock_discord_interaction, setup_database_service_mocks, setup_time_mocks


class TestProcessAbsenteesCmd(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from ironforgedbot.commands.admin.process_absentees import cmd_process_absentees
        self.cmd_process_absentees = cmd_process_absentees

        self.mock_interaction = create_mock_discord_interaction()

    @patch("ironforgedbot.commands.admin.process_absentees.time")
    @patch("ironforgedbot.commands.admin.process_absentees.format_duration")
    @patch("ironforgedbot.commands.admin.process_absentees.text_h2")
    @patch("ironforgedbot.commands.admin.process_absentees.discord.File")
    @patch("ironforgedbot.commands.admin.process_absentees.tabulate")
    @patch("ironforgedbot.commands.admin.process_absentees.db")
    @patch("ironforgedbot.commands.admin.process_absentees.AbsentMemberService")
    async def test_cmd_process_absentees_success(
        self,
        mock_absent_service_class,
        mock_db,
        mock_tabulate,
        mock_discord_file,
        mock_text_h2,
        mock_format_duration,
        mock_time
    ):
        setup_time_mocks(None, mock_time, duration_seconds=1.0)
        mock_format_duration.return_value = "1.0s"
        mock_text_h2.return_value = "## 🚿 Absentee List"
        
        mock_session, mock_absent_service = setup_database_service_mocks(mock_db, mock_absent_service_class)
        
        mock_member = Mock()
        mock_member.nickname = "member1"
        mock_member.date = "2023-01-01"
        mock_member.information = "info1"
        mock_member.comment = "comment1"
        
        mock_absent_service.process_absent_members = AsyncMock(return_value=[mock_member])
        
        mock_tabulate.return_value = "table_output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await self.cmd_process_absentees(self.mock_interaction)

        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=False
        )
        
        mock_absent_service_class.assert_called_once_with(mock_session)
        mock_absent_service.process_absent_members.assert_called_once()
        
        expected_data = [["member1", "2023-01-01", "info1", "comment1"]]
        mock_tabulate.assert_called_once_with(
            expected_data,
            headers=["Member", "Date", "Info", "Comment"],
            tablefmt="github"
        )
        
        mock_discord_file.assert_called_once()
        file_call_args = mock_discord_file.call_args
        self.assertEqual(file_call_args.kwargs["fp"].read(), b"table_output")
        self.assertTrue(file_call_args.kwargs["filename"].startswith("absentee_list_"))
        self.assertTrue(file_call_args.kwargs["filename"].endswith(".txt"))
        
        self.mock_interaction.followup.send.assert_called_once()
        send_call_args = self.mock_interaction.followup.send.call_args
        self.assertIn("## 🚿 Absentee List", send_call_args.args[0])
        self.assertIn("**1**", send_call_args.args[0])
        self.assertIn("**1.0s**", send_call_args.args[0])
        self.assertEqual(send_call_args.kwargs["file"], mock_file)

    @patch("ironforgedbot.commands.admin.process_absentees.time")
    @patch("ironforgedbot.commands.admin.process_absentees.format_duration")
    @patch("ironforgedbot.commands.admin.process_absentees.text_h2")
    @patch("ironforgedbot.commands.admin.process_absentees.discord.File")
    @patch("ironforgedbot.commands.admin.process_absentees.tabulate")
    @patch("ironforgedbot.commands.admin.process_absentees.db")
    @patch("ironforgedbot.commands.admin.process_absentees.AbsentMemberService")
    async def test_cmd_process_absentees_empty_list(
        self,
        mock_absent_service_class,
        mock_db,
        mock_tabulate,
        mock_discord_file,
        mock_text_h2,
        mock_format_duration,
        mock_time
    ):
        setup_time_mocks(None, mock_time, duration_seconds=0.5)
        mock_format_duration.return_value = "0.5s"
        mock_text_h2.return_value = "## 🚿 Absentee List"
        
        mock_session, mock_absent_service = setup_database_service_mocks(mock_db, mock_absent_service_class)
        mock_absent_service.process_absent_members = AsyncMock(return_value=[])
        
        mock_tabulate.return_value = "empty_table"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await self.cmd_process_absentees(self.mock_interaction)

        mock_tabulate.assert_called_once_with(
            [],
            headers=["Member", "Date", "Info", "Comment"],
            tablefmt="github"
        )
        
        send_call_args = self.mock_interaction.followup.send.call_args
        self.assertIn("**0**", send_call_args.args[0])
        self.assertIn("**0.5s**", send_call_args.args[0])