import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.config import CONFIG
from ironforgedcore.common.roles import ROLE
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestCmdAdmin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_require_role_patcher = patch(
            "ironforgedbot.decorators.require_role.require_role"
        )
        self.mock_require_role = self.mock_require_role_patcher.start()
        self.mock_require_role.side_effect = lambda *args, **kwargs: lambda func: func

        from ironforgedbot.commands.admin.cmd_admin import cmd_admin

        self.cmd_admin = cmd_admin

        test_member = create_test_member("TestUser", [ROLE.LEADERSHIP])
        test_member.id = 123456789
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

        self.mock_interaction.guild.get_member.return_value = test_member

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
            content="## 🤓 Administration Menu", view=mock_menu, ephemeral=True
        )
        self.assertEqual(mock_menu.message, mock_message)

    @patch("ironforgedbot.commands.admin.cmd_admin.get_text_channel")
    @patch("ironforgedbot.commands.admin.cmd_admin.send_error_response")
    async def test_cmd_admin_no_channel_found(
        self, mock_send_error_response, mock_get_text_channel
    ):
        mock_get_text_channel.return_value = None

        await self.cmd_admin(self.mock_interaction)

        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Error accessing report channel."
        )


class TestAdminMenuView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_channel = Mock()
        test_member = create_test_member("TestUser", [])
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

        with patch("discord.ui.View.__init__", return_value=None):
            from ironforgedbot.commands.admin.admin_menu_view import AdminMenuView

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

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_sync_members")
    async def test_member_sync_button(self, mock_cmd_sync_members):
        mock_cmd_sync_members.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_sync_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_sync_members.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_check_discrepancies")
    async def test_member_discrepancy_check_button(self, mock_cmd_check_discrepancies):
        mock_cmd_check_discrepancies.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_discrepancy_check_button(
            self.mock_interaction, mock_button
        )

        self.menu.clear_parent.assert_called_once()
        mock_cmd_check_discrepancies.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_check_activity")
    async def test_member_activity_check_button(self, mock_cmd_check_activity):
        mock_cmd_check_activity.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_activity_check_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_check_activity.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_refresh_ranks")
    async def test_member_rank_check_button(self, mock_cmd_refresh_ranks):
        mock_cmd_refresh_ranks.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.member_rank_check_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_refresh_ranks.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_view_logs")
    async def test_view_logs_button(self, mock_cmd_view_logs):
        mock_cmd_view_logs.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_logs_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_view_logs.assert_called_once_with(self.mock_interaction)

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_view_changelog")
    async def test_view_changelog_button(self, mock_cmd_view_changelog):
        mock_cmd_view_changelog.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_changelog_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_view_changelog.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_view_state")
    async def test_view_state_button(self, mock_cmd_view_state):
        mock_cmd_view_state.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.view_state_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_view_state.assert_called_once_with(self.mock_interaction)

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_process_absentees")
    async def test_process_absentee_list_button(self, mock_cmd_process_absentees):
        mock_cmd_process_absentees.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.process_absentee_list_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_cmd_process_absentees.assert_called_once_with(self.mock_interaction)

    @patch("ironforgedbot.commands.admin.admin_menu_view.cmd_change_discord_account")
    async def test_change_discord_account_button(self, mock_cmd_change_discord_account):
        mock_cmd_change_discord_account.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.change_discord_account_button(
            self.mock_interaction, mock_button
        )

        self.menu.clear_parent.assert_called_once()
        mock_cmd_change_discord_account.assert_called_once_with(
            self.mock_interaction, self.mock_channel
        )

    async def test_renamed_spin_buttons_have_old_suffix(self):
        buttons_by_id = {
            raw.__discord_ui_model_kwargs__.get(
                "custom_id"
            ): raw.__discord_ui_model_kwargs__
            for raw in self.AdminMenuView.__view_children_items__.values()
            if raw.__discord_ui_model_kwargs__.get("custom_id")
            and raw.__discord_ui_model_kwargs__.get("custom_id").startswith("spin_")
        }

        self.assertIn("spin_sotw_old", buttons_by_id)
        self.assertIn("spin_botw_old", buttons_by_id)
        self.assertIn("(old)", buttons_by_id["spin_sotw_old"]["label"])
        self.assertIn("(old)", buttons_by_id["spin_botw_old"]["label"])

    async def test_new_spin_placeholder_buttons_exist(self):
        buttons_by_id = {
            raw.__discord_ui_model_kwargs__.get(
                "custom_id"
            ): raw.__discord_ui_model_kwargs__
            for raw in self.AdminMenuView.__view_children_items__.values()
            if raw.__discord_ui_model_kwargs__.get("custom_id")
            and raw.__discord_ui_model_kwargs__.get("custom_id").startswith("spin_")
        }

        sotw_new = buttons_by_id.get("spin_sotw_new")
        botw_new = buttons_by_id.get("spin_botw_new")

        self.assertIsNotNone(sotw_new)
        self.assertIsNotNone(botw_new)
        self.assertIn("(new)", sotw_new["label"])
        self.assertIn("(new)", botw_new["label"])
        self.assertEqual(sotw_new["row"], 4)
        self.assertEqual(botw_new["row"], 4)

    @patch("ironforgedbot.commands.admin.admin_menu_view.get_text_channel")
    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_sotw_options")
    async def test_spin_sotw_new_opens_options_modal(
        self, mock_get_sotw_options, mock_spin_options_modal, mock_get_text_channel
    ):
        mock_target = Mock()
        mock_get_text_channel.return_value = mock_target
        mock_get_sotw_options.return_value = ["skill-a", "skill-b"]

        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_sotw_new_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_get_text_channel.assert_called_once_with(
            self.mock_interaction.guild, CONFIG.BOTW_SOTW_CHANNEL_ID
        )
        mock_spin_options_modal.assert_called_once()
        modal_args = mock_spin_options_modal.call_args[0]
        self.assertEqual(modal_args[0], "Spin SOTW (new)")
        self.assertEqual(modal_args[1], ["skill-a", "skill-b"])
        self.mock_interaction.response.send_modal.assert_called_once()

    @patch("ironforgedbot.commands.admin.admin_menu_view.get_text_channel")
    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_botw_options")
    async def test_spin_botw_new_opens_options_modal(
        self, mock_get_botw_options, mock_spin_options_modal, mock_get_text_channel
    ):
        mock_target = Mock()
        mock_get_text_channel.return_value = mock_target
        mock_get_botw_options.return_value = ["boss-a", "boss-b"]

        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_botw_new_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_get_text_channel.assert_called_once_with(
            self.mock_interaction.guild, CONFIG.BOTW_SOTW_CHANNEL_ID
        )
        mock_spin_options_modal.assert_called_once()
        modal_args = mock_spin_options_modal.call_args[0]
        self.assertEqual(modal_args[0], "Spin BOTW (new)")
        self.assertEqual(modal_args[1], ["boss-a", "boss-b"])
        self.mock_interaction.response.send_modal.assert_called_once()

    @patch("ironforgedbot.commands.admin.admin_menu_view.send_error_response")
    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_text_channel")
    async def test_spin_sotw_new_channel_not_found_sends_error(
        self,
        mock_get_text_channel,
        mock_spin_options_modal,
        mock_send_error_response,
    ):
        mock_get_text_channel.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_sotw_new_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Spinning channel not configured."
        )
        mock_spin_options_modal.assert_not_called()
        self.mock_interaction.response.send_modal.assert_not_called()

    @patch("ironforgedbot.commands.admin.admin_menu_view.send_error_response")
    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_text_channel")
    async def test_spin_botw_new_channel_not_found_sends_error(
        self,
        mock_get_text_channel,
        mock_spin_options_modal,
        mock_send_error_response,
    ):
        mock_get_text_channel.return_value = None
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_botw_new_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Spinning channel not configured."
        )
        mock_spin_options_modal.assert_not_called()
        self.mock_interaction.response.send_modal.assert_not_called()

    @patch("ironforgedbot.commands.admin.admin_menu_view.post_weekly_spin_result")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_text_channel")
    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_sotw_options")
    async def test_spin_sotw_new_submits_to_target_channel(
        self,
        mock_get_sotw_options,
        mock_spin_options_modal,
        mock_get_text_channel,
        mock_post_weekly_spin_result,
    ):
        mock_target = Mock()
        mock_get_text_channel.return_value = mock_target
        mock_get_sotw_options.return_value = []
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_sotw_new_button(self.mock_interaction, mock_button)

        on_result = mock_spin_options_modal.call_args[0][2]
        mock_file = Mock()
        await on_result(self.mock_interaction, mock_file, "Agility")

        mock_post_weekly_spin_result.assert_called_once_with(
            mock_target, "sotw", [], mock_file, "Agility"
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.post_weekly_spin_result")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_text_channel")
    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_botw_options")
    async def test_spin_botw_new_submits_to_target_channel(
        self,
        mock_get_botw_options,
        mock_spin_options_modal,
        mock_get_text_channel,
        mock_post_weekly_spin_result,
    ):
        mock_target = Mock()
        mock_get_text_channel.return_value = mock_target
        mock_get_botw_options.return_value = []
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_botw_new_button(self.mock_interaction, mock_button)

        on_result = mock_spin_options_modal.call_args[0][2]
        mock_file = Mock()
        await on_result(self.mock_interaction, mock_file, "Zulrah")

        mock_post_weekly_spin_result.assert_called_once_with(
            mock_target, "botw", [], mock_file, "Zulrah"
        )

    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_sotw_options")
    async def test_renamed_sotw_button_still_opens_options_modal(
        self, mock_get_sotw_options, mock_spin_options_modal
    ):
        mock_get_sotw_options.return_value = []
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_sotw_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_spin_options_modal.assert_called_once()
        modal_title = mock_spin_options_modal.call_args[0][0]
        self.assertIn("(old)", modal_title)

    @patch("ironforgedbot.commands.admin.admin_menu_view.SpinOptionsModal")
    @patch("ironforgedbot.commands.admin.admin_menu_view.get_botw_options")
    async def test_renamed_botw_button_still_opens_options_modal(
        self, mock_get_botw_options, mock_spin_options_modal
    ):
        mock_get_botw_options.return_value = []
        self.menu.clear_parent = AsyncMock()
        mock_button = Mock()

        await self.menu.spin_botw_button(self.mock_interaction, mock_button)

        self.menu.clear_parent.assert_called_once()
        mock_spin_options_modal.assert_called_once()
        modal_title = mock_spin_options_modal.call_args[0][0]
        self.assertIn("(old)", modal_title)
