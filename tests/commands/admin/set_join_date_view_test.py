import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import discord

from tests.helpers import create_mock_discord_interaction, create_test_member


def _make_member(member_id: int, display_name: str) -> Mock:
    member = Mock(spec=discord.Member)
    member.id = member_id
    member.display_name = display_name
    member.global_name = display_name
    member.mention = f"<@{member_id}>"
    return member


def _make_interaction(guild: Mock | None = None) -> Mock:
    interaction = create_mock_discord_interaction(
        user=create_test_member("AdminUser", ["Leadership"])
    )
    interaction.guild = guild
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.followup.send_modal = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.original_response = AsyncMock(return_value=Mock(spec=discord.Message))
    return interaction


class TestSetJoinDateView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = Mock(spec=discord.Guild)
        self.report_channel = Mock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()

        from ironforgedbot.commands.admin.set_join_date_view import SetJoinDateView

        self.view = SetJoinDateView(
            report_channel=self.report_channel,
            guild=self.guild,
        )

        self.target_user = _make_member(777, "TargetUser")
        self.target_joined = datetime(2024, 3, 1, tzinfo=timezone.utc)
        self.mock_interaction = _make_interaction(guild=self.guild)

    def test_continue_button_disabled_until_member_selected(self):
        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "set_join_date_continue"
        )
        self.assertTrue(continue_btn.disabled)

        self.view.target_member = self.target_user
        self.view._sync_button_state()
        self.assertTrue(continue_btn.disabled)

        self.view.target_joined_date = self.target_joined
        self.view._sync_button_state()
        self.assertFalse(continue_btn.disabled)

    @patch(
        "ironforgedbot.commands.admin.set_join_date_view.datetime_to_discord_relative"
    )
    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_member_select_updates_state_with_current_date(
        self, mock_db, mock_create, mock_format
    ):
        mock_format.side_effect = lambda dt, fmt: f"<DT:{fmt}>"

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        db_member = Mock()
        db_member.joined_date = self.target_joined
        db_member.active = True
        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        mock_create.return_value = mock_service

        select = self.view.member_select
        with patch.object(
            type(select), "values", new_callable=PropertyMock
        ) as mock_vals:
            mock_vals.return_value = [self.target_user]
            await select.callback(self.mock_interaction)

        self.assertEqual(self.view.target_member, self.target_user)
        self.assertEqual(self.view.target_joined_date, self.target_joined)
        self.mock_interaction.response.edit_message.assert_called_once()
        embed = self.mock_interaction.response.edit_message.call_args.kwargs["embed"]
        self.assertIn("Current join date", embed.description)
        self.assertIn("<DT:d>", embed.description)
        self.assertIn("<DT:R>", embed.description)
        mock_format.assert_any_call(self.target_joined, "d")
        mock_format.assert_any_call(self.target_joined, "R")

    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_member_select_rejects_unregistered(self, mock_db, mock_create):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        mock_create.return_value = mock_service

        select = self.view.member_select
        with patch.object(
            type(select), "values", new_callable=PropertyMock
        ) as mock_vals:
            mock_vals.return_value = [self.target_user]
            await select.callback(self.mock_interaction)

        self.assertIsNone(self.view.target_member)
        self.assertIsNone(self.view.target_joined_date)
        embed = self.mock_interaction.response.edit_message.call_args.kwargs["embed"]
        self.assertIn("not registered", embed.description.lower())
        self.assertIn("not an active member", embed.description.lower())

        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "set_join_date_continue"
        )
        self.assertTrue(continue_btn.disabled)

    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_member_select_rejects_inactive(self, mock_db, mock_create):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        db_member = Mock()
        db_member.joined_date = self.target_joined
        db_member.active = False
        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        mock_create.return_value = mock_service

        select = self.view.member_select
        with patch.object(
            type(select), "values", new_callable=PropertyMock
        ) as mock_vals:
            mock_vals.return_value = [self.target_user]
            await select.callback(self.mock_interaction)

        self.assertIsNone(self.view.target_member)
        self.assertIsNone(self.view.target_joined_date)

        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "set_join_date_continue"
        )
        self.assertTrue(continue_btn.disabled)

    @patch("ironforgedbot.commands.admin.set_join_date_view.SetJoinDateModal")
    async def test_continue_opens_modal(self, mock_modal_cls):
        mock_modal = MagicMock()
        mock_modal_cls.return_value = mock_modal

        self.view.target_member = self.target_user
        self.view.target_joined_date = self.target_joined

        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "set_join_date_continue"
        )
        await continue_btn.callback(self.mock_interaction)

        mock_modal_cls.assert_called_once()
        kwargs = mock_modal_cls.call_args.kwargs
        self.assertEqual(kwargs["target_user"], self.target_user)
        self.assertEqual(kwargs["original_date"], self.target_joined)
        self.assertEqual(kwargs["admin_discord_id"], self.mock_interaction.user.id)
        self.mock_interaction.response.send_modal.assert_called_once_with(mock_modal)
        self.mock_interaction.followup.send_modal.assert_not_called()

    async def test_continue_with_no_target_does_nothing(self):
        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "set_join_date_continue"
        )
        await continue_btn.callback(self.mock_interaction)

        self.mock_interaction.response.send_modal.assert_not_called()
        self.mock_interaction.followup.send_modal.assert_not_called()


class TestSetJoinDateModal(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target_user = _make_member(777, "TargetUser")
        self.original_date = datetime(2024, 3, 1, tzinfo=timezone.utc)
        self.report_channel = Mock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()
        self.mock_interaction = _make_interaction()

        from ironforgedbot.commands.admin.set_join_date_view import SetJoinDateModal

        self.modal = SetJoinDateModal(
            target_user=self.target_user,
            original_date=self.original_date,
            report_channel=self.report_channel,
            admin_discord_id=999,
        )

    def test_placeholder_uses_iso_date(self):
        self.assertEqual(
            self.modal.children[0].placeholder,
            self.original_date.strftime("%Y-%m-%d"),
        )

    @patch("ironforgedbot.commands.admin.set_join_date_view._execute_set")
    async def test_valid_date_sends_ephemeral_ack(self, mock_execute):
        mock_execute.return_value = None
        self.modal.date_input._value = "2024-06-15"

        await self.modal.on_submit(self.mock_interaction)

        mock_execute.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once()
        args = self.mock_interaction.followup.send.call_args.args
        self.assertEqual(args[0], ":white_check_mark: Join date updated.")
        self.assertTrue(
            self.mock_interaction.followup.send.call_args.kwargs["ephemeral"]
        )
        self.mock_interaction.edit_original_response.assert_not_called()

    @patch("ironforgedbot.commands.admin.set_join_date_view.send_ephemeral_error")
    @patch("ironforgedbot.commands.admin.set_join_date_view._execute_set")
    async def test_malformed_date_does_not_call_execute(self, mock_execute, mock_error):
        self.modal.date_input._value = "not-a-date"

        await self.modal.on_submit(self.mock_interaction)

        mock_execute.assert_not_called()
        mock_error.assert_called_once()

    @patch("ironforgedbot.commands.admin.set_join_date_view.send_ephemeral_error")
    @patch("ironforgedbot.commands.admin.set_join_date_view._execute_set")
    async def test_future_date_rejected(self, mock_execute, mock_error):
        future = datetime.now(timezone.utc).date()
        self.modal.date_input._value = future.replace(year=future.year + 1).strftime(
            "%Y-%m-%d"
        )

        await self.modal.on_submit(self.mock_interaction)

        mock_execute.assert_not_called()
        mock_error.assert_called_once()

    @patch("ironforgedbot.commands.admin.set_join_date_view._execute_set")
    async def test_today_date_accepted(self, mock_execute):
        mock_execute.return_value = None
        self.modal.date_input._value = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        await self.modal.on_submit(self.mock_interaction)

        mock_execute.assert_called_once()

    @patch("ironforgedbot.commands.admin.set_join_date_view.send_ephemeral_error")
    @patch("ironforgedbot.commands.admin.set_join_date_view._execute_set")
    async def test_db_update_failure_routes_to_ephemeral_error(
        self, mock_execute, mock_error
    ):
        mock_execute.return_value = Mock(spec=discord.Embed, description="DB crashed")
        self.modal.date_input._value = "2024-06-15"

        await self.modal.on_submit(self.mock_interaction)

        mock_error.assert_called_once()
        self.mock_interaction.followup.send.assert_not_called()


class TestExecuteSet(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target_user = _make_member(777, "TargetUser")
        self.new_date = datetime(2024, 6, 15, tzinfo=timezone.utc)
        self.report_channel = Mock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()

    @patch(
        "ironforgedbot.commands.admin.set_join_date_view.datetime_to_discord_relative"
    )
    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_success_returns_none_and_posts_audit(
        self, mock_db, mock_create, mock_format
    ):
        mock_format.side_effect = lambda dt, fmt: f"<DT:{fmt}>"

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        previous = datetime(2024, 1, 1, tzinfo=timezone.utc)
        db_member = Mock()
        db_member.id = "target-db-id"
        db_member.joined_date = previous

        admin = Mock()
        admin.id = "admin-db-id"

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(
            side_effect=[db_member, admin]
        )
        mock_service.change_joined_date = AsyncMock(return_value=db_member)
        mock_create.return_value = mock_service

        from ironforgedbot.commands.admin.set_join_date_view import _execute_set

        result = await _execute_set(
            target_user=self.target_user,
            new_date=self.new_date,
            report_channel=self.report_channel,
            admin_discord_id=999,
        )

        self.assertIsNone(result)
        mock_service.change_joined_date.assert_called_once_with(
            id="target-db-id",
            new_joined_date=self.new_date,
            admin_id="admin-db-id",
            comment="Manually set join date",
        )
        self.report_channel.send.assert_called_once()
        report_text = self.report_channel.send.call_args.args[0]
        self.assertIn("set join date for", report_text)
        self.assertIn("<DT:d>", report_text)
        self.assertIn("→", report_text)
        mock_format.assert_any_call(previous, "d")
        mock_format.assert_any_call(self.new_date, "d")

    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_member_not_registered_returns_error_embed(
        self, mock_db, mock_create
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        mock_create.return_value = mock_service

        from ironforgedbot.commands.admin.set_join_date_view import _execute_set

        result = await _execute_set(
            target_user=self.target_user,
            new_date=self.new_date,
            report_channel=self.report_channel,
        )

        self.assertIsNotNone(result)
        self.assertIn("Member not registered", result.title)
        self.report_channel.send.assert_called_once()

    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_db_change_raises_returns_error_embed(self, mock_db, mock_create):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        db_member = Mock()
        db_member.id = "target-db-id"
        db_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        mock_service.change_joined_date = AsyncMock(
            side_effect=RuntimeError("DB crashed")
        )
        mock_create.return_value = mock_service

        from ironforgedbot.commands.admin.set_join_date_view import _execute_set

        result = await _execute_set(
            target_user=self.target_user,
            new_date=self.new_date,
            report_channel=self.report_channel,
        )

        self.assertIsNotNone(result)
        self.assertIn("DB update failed", result.title)
        self.report_channel.send.assert_called_once()

    @patch(
        "ironforgedbot.commands.admin.set_join_date_view.datetime_to_discord_relative"
    )
    @patch("ironforgedbot.commands.admin.set_join_date_view.create_member_service")
    @patch("ironforgedbot.commands.admin.set_join_date_view.db")
    async def test_works_without_admin_db_record(
        self, mock_db, mock_create, mock_format
    ):
        mock_format.side_effect = lambda dt, fmt: f"<DT:{fmt}>"

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        db_member = Mock()
        db_member.id = "target-db-id"
        db_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(side_effect=[db_member, None])
        mock_service.change_joined_date = AsyncMock(return_value=db_member)
        mock_create.return_value = mock_service

        from ironforgedbot.commands.admin.set_join_date_view import _execute_set

        result = await _execute_set(
            target_user=self.target_user,
            new_date=self.new_date,
            report_channel=self.report_channel,
            admin_discord_id=999,
        )

        self.assertIsNone(result)
        call_kwargs = mock_service.change_joined_date.call_args.kwargs
        self.assertIsNone(call_kwargs["admin_id"])


class TestCmdSetJoinDate(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.admin.set_join_date_view.SetJoinDateView")
    async def test_sends_ephemeral_view(self, mock_view_cls):
        interaction = _make_interaction(guild=Mock(spec=discord.Guild))
        report_channel = Mock(spec=discord.TextChannel)

        mock_view = MagicMock()
        mock_view_cls.return_value = mock_view
        mock_view._build_embed = MagicMock(return_value=Mock(spec=discord.Embed))

        from ironforgedbot.commands.admin.set_join_date_view import cmd_set_join_date

        await cmd_set_join_date(interaction, report_channel)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()
        kwargs = interaction.followup.send.call_args.kwargs
        self.assertTrue(kwargs["ephemeral"])
        self.assertIn("view", kwargs)
        self.assertIn("embed", kwargs)
