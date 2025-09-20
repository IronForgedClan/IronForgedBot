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

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_sync_members")
    async def test_member_sync_button(self, mock_cmd_sync_members):
        mock_cmd_sync_members.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_sync_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_sync_members.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_check_discrepancies")
    async def test_member_discrepancy_check_button(self, mock_cmd_check_discrepancies):
        mock_cmd_check_discrepancies.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_discrepancy_check_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_check_discrepancies.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_check_activity")
    async def test_member_activity_check_button(self, mock_cmd_check_activity):
        mock_cmd_check_activity.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_activity_check_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_check_activity.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_refresh_ranks")
    async def test_member_rank_check_button(self, mock_cmd_refresh_ranks):
        mock_cmd_refresh_ranks.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_rank_check_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_refresh_ranks.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_view_logs")
    async def test_view_logs_button(self, mock_cmd_view_logs):
        mock_cmd_view_logs.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_logs_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_view_logs.assert_called_once_with(self.mock_interaction)

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_view_state")
    async def test_view_state_button(self, mock_cmd_view_state):
        mock_cmd_view_state.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_state_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_view_state.assert_called_once_with(self.mock_interaction)

    @patch("ironforgedbot.commands.admin.cmd_admin.cmd_process_absentees")
    async def test_process_absentee_list_button(self, mock_cmd_process_absentees):
        mock_cmd_process_absentees.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.process_absentee_list_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_process_absentees.assert_called_once_with(self.mock_interaction)