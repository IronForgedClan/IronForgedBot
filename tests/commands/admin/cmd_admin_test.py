import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE


class TestCmdAdmin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_require_role_patcher = patch(
            "ironforgedbot.decorators.require_role"
        )
        self.mock_require_role = self.mock_require_role_patcher.start()
        self.mock_require_role.side_effect = lambda *args, **kwargs: lambda func: func

        from ironforgedbot.commands.admin.cmd_admin import cmd_admin
        self.cmd_admin = cmd_admin

        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.guild = Mock()
        self.mock_interaction.user = Mock()
        self.mock_interaction.user.display_name = "TestUser"
        self.mock_interaction.user.id = 123456789
        
        mock_member = Mock()
        mock_member.display_name = "TestUser"
        mock_role = Mock()
        mock_role.name = ROLE.LEADERSHIP
        mock_member.roles = [mock_role]
        
        self.mock_interaction.guild.get_member.return_value = mock_member
        
        self.mock_interaction.response.defer = AsyncMock()
        self.mock_interaction.followup.send = AsyncMock()

    def tearDown(self):
        self.mock_require_role_patcher.stop()

    @patch("ironforgedbot.commands.admin.cmd_admin.get_text_channel")
    @patch("ironforgedbot.commands.admin.cmd_admin.AdminMenuView")
    async def test_cmd_admin_success(self, mock_admin_menu_view, mock_get_text_channel):
        mock_channel = Mock()
        mock_get_text_channel.return_value = mock_channel
        mock_menu = Mock()
        mock_admin_menu_view.return_value = mock_menu
        mock_message = Mock()
        self.mock_interaction.followup.send.return_value = mock_message

        await self.cmd_admin(self.mock_interaction)

        mock_get_text_channel.assert_called_once()
        mock_admin_menu_view.assert_called_once_with(report_channel=mock_channel)
        self.mock_interaction.followup.send.assert_called_once_with(
            content="## 🤓 Administration Menu", view=mock_menu
        )
        self.assertEqual(mock_menu.message, mock_message)

    @patch("ironforgedbot.commands.admin.cmd_admin.get_text_channel")
    @patch("ironforgedbot.commands.admin.cmd_admin.send_error_response")
    async def test_cmd_admin_no_channel_found(self, mock_send_error_response, mock_get_text_channel):
        mock_get_text_channel.return_value = None

        await self.cmd_admin(self.mock_interaction)

        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Error accessing report channel."
        )


class TestAdminMenuView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_channel = Mock()
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.guild = Mock()
        self.mock_interaction.user = Mock()
        self.mock_interaction.user.display_name = "TestUser"
        self.mock_interaction.response.send_message = AsyncMock()
        self.mock_interaction.response.defer = AsyncMock()
        self.mock_interaction.followup.send = AsyncMock()

        with patch("discord.ui.View.__init__", return_value=None):
            from ironforgedbot.commands.admin.cmd_admin import AdminMenuView
            self.AdminMenuView = AdminMenuView
            self.menu = self.AdminMenuView(report_channel=self.mock_channel)

    async def test_admin_menu_view_initialization(self):
        with patch("discord.ui.View.__init__", return_value=None):
            menu = self.AdminMenuView(report_channel=self.mock_channel)
            self.assertEqual(menu.report_channel, self.mock_channel)
            self.assertIsNone(menu.message)

    async def test_admin_menu_view_custom_timeout(self):
        with patch("discord.ui.View.__init__", return_value=None):
            menu = self.AdminMenuView(report_channel=self.mock_channel, timeout=300)
            self.assertEqual(menu.report_channel, self.mock_channel)

    async def test_clear_parent_with_message(self):
        mock_message = Mock()
        mock_message.delete = AsyncMock()
        self.menu.message = mock_message

        await self.menu.clear_parent()

        mock_message.delete.assert_called_once()

    async def test_clear_parent_without_message(self):
        self.menu.message = None

        await self.menu.clear_parent()

    async def test_on_timeout_calls_clear_parent(self):
        self.menu.clear_parent = AsyncMock()

        await self.menu.on_timeout()

        self.menu.clear_parent.assert_called_once()

    @patch("ironforgedbot.commands.admin.cmd_admin.job_sync_members")
    async def test_member_sync_button(self, mock_job_sync_members):
        mock_job_sync_members.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_sync_button(self.mock_interaction, mock_button)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating member sync job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])
        self.menu.clear_parent.assert_called_once()
        mock_job_sync_members.assert_called_once_with(
            self.mock_interaction.guild, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.job_check_membership_discrepancies")
    @patch("ironforgedbot.commands.admin.cmd_admin.CONFIG")
    async def test_member_discrepancy_check_button(self, mock_config, mock_job_check):
        mock_config.WOM_API_KEY = "test_api_key"
        mock_config.WOM_GROUP_ID = "test_group_id"
        mock_job_check.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_discrepancy_check_button(self.mock_interaction, mock_button)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating member discrepancy job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])
        self.menu.clear_parent.assert_called_once()
        mock_job_check.assert_called_once_with(
            self.mock_interaction.guild,
            self.mock_channel,
            "test_api_key",
            "test_group_id"
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.job_check_activity")
    @patch("ironforgedbot.commands.admin.cmd_admin.CONFIG")
    async def test_member_activity_check_button(self, mock_config, mock_job_check_activity):
        mock_config.WOM_API_KEY = "test_api_key"
        mock_config.WOM_GROUP_ID = "test_group_id"
        mock_job_check_activity.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_activity_check_button(self.mock_interaction, mock_button)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating activity check job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])
        self.menu.clear_parent.assert_called_once()
        mock_job_check_activity.assert_called_once_with(
            self.mock_channel, "test_api_key", "test_group_id"
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.job_refresh_ranks")
    async def test_member_rank_check_button(self, mock_job_refresh_ranks):
        mock_job_refresh_ranks.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_rank_check_button(self.mock_interaction, mock_button)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("Manually initiating rank check job", call_args.args[0])
        self.assertTrue(call_args.kwargs["ephemeral"])
        self.menu.clear_parent.assert_called_once()
        mock_job_refresh_ranks.assert_called_once_with(
            self.mock_interaction.guild, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.get_latest_log_file")
    @patch("ironforgedbot.commands.admin.cmd_admin.send_error_response")
    async def test_view_logs_button_success(self, mock_send_error_response, mock_get_latest_log):
        mock_file = Mock()
        mock_get_latest_log.return_value = mock_file
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_logs_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_get_latest_log.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once_with(
            content="## Latest Log File", file=mock_file
        )
        mock_send_error_response.assert_not_called()

    @patch("ironforgedbot.commands.admin.cmd_admin.get_latest_log_file")
    @patch("ironforgedbot.commands.admin.cmd_admin.send_error_response")
    async def test_view_logs_button_no_file(self, mock_send_error_response, mock_get_latest_log):
        mock_get_latest_log.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_logs_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_get_latest_log.assert_called_once()
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Error processing log file."
        )
        self.mock_interaction.followup.send.assert_not_called()

    @patch("ironforgedbot.commands.admin.cmd_admin.get_internal_state")
    async def test_view_state_button(self, mock_get_internal_state):
        mock_file = Mock()
        mock_get_internal_state.return_value = mock_file
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_state_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_get_internal_state.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once_with(
            content="## Current Internal State", file=mock_file
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.time.perf_counter")
    @patch("ironforgedbot.commands.admin.cmd_admin.format_duration")
    @patch("ironforgedbot.commands.admin.cmd_admin.text_h2")
    @patch("ironforgedbot.commands.admin.cmd_admin.discord.File")
    @patch("ironforgedbot.commands.admin.cmd_admin.tabulate")
    @patch("ironforgedbot.commands.admin.cmd_admin.db.get_session")
    @patch("ironforgedbot.commands.admin.cmd_admin.AbsentMemberService")
    async def test_process_absentee_list_button(
        self,
        mock_absent_service_class,
        mock_get_session,
        mock_tabulate,
        mock_discord_file,
        mock_text_h2,
        mock_format_duration,
        mock_perf_counter
    ):
        mock_perf_counter.side_effect = [1.0, 2.0]
        mock_format_duration.return_value = "1.0s"
        mock_text_h2.return_value = "## 🚿 Absentee List"
        
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_absent_service = Mock()
        mock_absent_service_class.return_value = mock_absent_service
        
        mock_member1 = Mock()
        mock_member1.nickname = "member1"
        mock_member1.date = "2023-01-01"
        mock_member1.information = "info1"
        mock_member1.comment = "comment1"
        
        mock_member2 = Mock()
        mock_member2.nickname = "member2"
        mock_member2.date = "2023-01-02"
        mock_member2.information = "info2"
        mock_member2.comment = "comment2"
        
        mock_absent_service.process_absent_members = AsyncMock(return_value=[mock_member1, mock_member2])
        
        mock_tabulate.return_value = "table_output"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file
        
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.process_absentee_list_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=False
        )
        
        mock_absent_service_class.assert_called_once_with(mock_session)
        mock_absent_service.process_absent_members.assert_called_once()
        
        expected_data = [
            ["member1", "2023-01-01", "info1", "comment1"],
            ["member2", "2023-01-02", "info2", "comment2"]
        ]
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
        self.assertIn("**2**", send_call_args.args[0])
        self.assertIn("**1.0s**", send_call_args.args[0])
        self.assertEqual(send_call_args.kwargs["file"], mock_file)

    @patch("ironforgedbot.commands.admin.cmd_admin.time.perf_counter")
    @patch("ironforgedbot.commands.admin.cmd_admin.format_duration")
    @patch("ironforgedbot.commands.admin.cmd_admin.text_h2")
    @patch("ironforgedbot.commands.admin.cmd_admin.discord.File")
    @patch("ironforgedbot.commands.admin.cmd_admin.tabulate")
    @patch("ironforgedbot.commands.admin.cmd_admin.db.get_session")
    @patch("ironforgedbot.commands.admin.cmd_admin.AbsentMemberService")
    async def test_process_absentee_list_button_empty_list(
        self,
        mock_absent_service_class,
        mock_get_session,
        mock_tabulate,
        mock_discord_file,
        mock_text_h2,
        mock_format_duration,
        mock_perf_counter
    ):
        mock_perf_counter.side_effect = [1.0, 1.5]
        mock_format_duration.return_value = "0.5s"
        mock_text_h2.return_value = "## 🚿 Absentee List"
        
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session
        
        mock_absent_service = Mock()
        mock_absent_service_class.return_value = mock_absent_service
        mock_absent_service.process_absent_members = AsyncMock(return_value=[])
        
        mock_tabulate.return_value = "empty_table"
        mock_file = Mock()
        mock_discord_file.return_value = mock_file
        
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.process_absentee_list_button(self.mock_interaction, mock_button)

        mock_tabulate.assert_called_once_with(
            [],
            headers=["Member", "Date", "Info", "Comment"],
            tablefmt="github"
        )
        
        send_call_args = self.mock_interaction.followup.send.call_args
        self.assertIn("**0**", send_call_args.args[0])
        self.assertIn("**0.5s**", send_call_args.args[0])