import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import discord

from ironforgedbot.commands.admin.view_changelog import ChangelogSelectView
from ironforgedcore.common.changelog_labels import CHANGE_TYPE_LABELS
from ironforgedcore.models.changelog import Changelog, ChangeType
from ironforgedcore.models.member import Member
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_member,
)

ADMIN_ID = 999001


@patch.dict("os.environ", VALID_CONFIG)
class _Base(unittest.TestCase):
    pass


def _make_changelog_entry(
    id=1,
    member_id="member-uuid",
    admin_id=None,
    change_type=ChangeType.ADD_INGOTS,
    previous_value="0",
    new_value="100",
    comment=None,
    timestamp=None,
):
    return Changelog(
        id=id,
        member_id=member_id,
        admin_id=admin_id,
        change_type=change_type,
        previous_value=previous_value,
        new_value=new_value,
        comment=comment,
        timestamp=timestamp or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_db_member(
    id="member-uuid",
    discord_id=4242,
    nickname="TestUser",
    active=True,
    joined_date=None,
):
    member = Mock(spec=Member)
    member.id = id
    member.discord_id = discord_id
    member.nickname = nickname
    member.active = active
    member.joined_date = joined_date or datetime(2024, 6, 1, tzinfo=timezone.utc)
    return member


def _make_admin_member(id="admin-uuid", nickname="AdminUser"):
    admin = Mock(spec=Member)
    admin.id = id
    admin.nickname = nickname
    return admin


class TestCmdViewChangelog(_Base, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_require_role_patcher = patch(
            "ironforgedbot.decorators.require_role.require_role"
        )
        self.mock_require_role = self.mock_require_role_patcher.start()
        self.mock_require_role.side_effect = lambda *args, **kwargs: lambda func: func

        from ironforgedbot.commands.admin.view_changelog import cmd_view_changelog

        self.cmd_view_changelog = cmd_view_changelog

        test_member = create_test_member("AdminUser", [])
        test_member.id = ADMIN_ID
        self.mock_interaction = create_mock_discord_interaction(user=test_member)
        self.mock_report_channel = AsyncMock(spec=discord.TextChannel)

    def tearDown(self):
        self.mock_require_role_patcher.stop()

    @patch("ironforgedbot.commands.admin.view_changelog.ChangelogSelectView")
    async def test_cmd_view_changelog_defers_and_shows_select(self, mock_view_cls):
        mock_view = Mock()
        mock_message = Mock()
        mock_view_cls.return_value = mock_view
        self.mock_interaction.followup.send.return_value = mock_message

        await self.cmd_view_changelog(self.mock_interaction, self.mock_report_channel)

        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_view_cls.assert_called_once_with(report_channel=self.mock_report_channel)
        self.mock_interaction.followup.send.assert_called_once()
        send_kwargs = self.mock_interaction.followup.send.call_args.kwargs
        self.assertEqual(send_kwargs["view"], mock_view)
        self.assertTrue(send_kwargs["ephemeral"])
        self.assertEqual(mock_view.message, mock_message)


class TestChangelogSelectView(_Base, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_db_patcher = patch("ironforgedbot.commands.admin.view_changelog.db")
        self.mock_db = self.mock_db_patcher.start()

        self.mock_create_member_service_patcher = patch(
            "ironforgedbot.commands.admin.view_changelog.create_member_service"
        )
        self.mock_create_member_service = (
            self.mock_create_member_service_patcher.start()
        )

        self.mock_create_changelog_service_patcher = patch(
            "ironforgedbot.commands.admin.view_changelog.create_changelog_service"
        )
        self.mock_create_changelog_service = (
            self.mock_create_changelog_service_patcher.start()
        )

        self.mock_send_error_patcher = patch(
            "ironforgedbot.commands.admin.view_changelog.send_error_response"
        )
        self.mock_send_error = self.mock_send_error_patcher.start()

        self.mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = self.mock_session
        mock_ctx.__aexit__.return_value = None
        self.mock_db.get_session.return_value = mock_ctx

        self.mock_member_service = AsyncMock()
        self.mock_changelog_service = AsyncMock()
        self.mock_create_member_service.return_value = self.mock_member_service
        self.mock_create_changelog_service.return_value = self.mock_changelog_service

        self.mock_report_channel = AsyncMock(spec=discord.TextChannel)
        self.view = ChangelogSelectView(report_channel=self.mock_report_channel)
        self.view.message = AsyncMock()

        self.target_discord_id = 4242
        self.target = create_test_member("TargetUser", [])
        self.target.id = self.target_discord_id

        self.mock_interaction = create_mock_discord_interaction()

        # The @discord.ui.select decorator replaces member_select with a
        # UserSelect item appended to view.children. Discord passes the user's
        # picks through the item's ``values`` property at dispatch time.
        self.select_item = self.view.children[0]
        self._values_patch = patch.object(
            type(self.select_item), "values", new_callable=PropertyMock
        )
        self._values_mock = self._values_patch.start()
        self._values_mock.return_value = [self.target]

    def tearDown(self):
        self._values_patch.stop()
        self.mock_db_patcher.stop()
        self.mock_create_member_service_patcher.stop()
        self.mock_create_changelog_service_patcher.stop()
        self.mock_send_error_patcher.stop()

    async def test_member_select_sends_file_only_for_active_member(self):
        db_member = _make_db_member(
            discord_id=self.target_discord_id, nickname="TargetUser"
        )
        self.mock_member_service.get_member_by_discord_id.return_value = db_member

        admin_member = _make_admin_member()
        entries = [
            _make_changelog_entry(
                id=2,
                admin_id="admin-uuid",
                change_type=ChangeType.ADD_INGOTS,
                previous_value="0",
                new_value="500",
                comment="Reward",
                timestamp=datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
            _make_changelog_entry(
                id=1,
                change_type=ChangeType.RANK_CHANGE,
                previous_value="Iron",
                new_value="Steel",
                comment=None,
                timestamp=datetime(2025, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]
        for entry in entries:
            entry.admin_member = admin_member
        self.mock_changelog_service.get_changelog_for_member.return_value = entries

        with patch(
            "ironforgedbot.commands.admin.view_changelog.discord.File"
        ) as mock_file_cls:
            mock_file = Mock()
            mock_file_cls.return_value = mock_file

            await self.select_item.callback(self.mock_interaction)

        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        self.mock_member_service.get_member_by_discord_id.assert_called_once_with(
            self.target_discord_id
        )
        self.mock_changelog_service.get_changelog_for_member.assert_called_once_with(
            self.target_discord_id, days=30
        )
        self.mock_send_error.assert_not_called()

        self.mock_interaction.followup.send.assert_called_once()
        send_kwargs = self.mock_interaction.followup.send.call_args.kwargs
        self.assertEqual(send_kwargs["file"], mock_file)
        self.assertTrue(send_kwargs["ephemeral"])
        self.assertNotIn("embed", send_kwargs)
        self.assertNotIn("content", send_kwargs)

        mock_file_cls.assert_called_once()
        file_kwargs = mock_file_cls.call_args.kwargs
        self.assertTrue(file_kwargs["filename"].startswith("changelog_targetuser_"))
        self.assertTrue(file_kwargs["filename"].endswith(".txt"))

    async def test_member_select_db_member_missing_sends_error(self):
        self.mock_member_service.get_member_by_discord_id.return_value = None

        await self.select_item.callback(self.mock_interaction)

        self.mock_send_error.assert_called_once()
        self.mock_changelog_service.get_changelog_for_member.assert_not_called()
        self.mock_interaction.followup.send.assert_not_called()

    async def test_member_select_inactive_member_sends_error(self):
        db_member = _make_db_member(discord_id=self.target_discord_id, active=False)
        self.mock_member_service.get_member_by_discord_id.return_value = db_member

        await self.select_item.callback(self.mock_interaction)

        self.mock_send_error.assert_called_once()
        self.mock_changelog_service.get_changelog_for_member.assert_not_called()
        self.mock_interaction.followup.send.assert_not_called()

    async def test_member_select_empty_changelog_still_sends_file(self):
        db_member = _make_db_member(discord_id=self.target_discord_id)
        self.mock_member_service.get_member_by_discord_id.return_value = db_member
        self.mock_changelog_service.get_changelog_for_member.return_value = []

        with patch(
            "ironforgedbot.commands.admin.view_changelog.discord.File"
        ) as mock_file_cls:
            mock_file = Mock()
            mock_file_cls.return_value = mock_file

            await self.select_item.callback(self.mock_interaction)

        self.mock_send_error.assert_not_called()
        self.mock_interaction.followup.send.assert_called_once()
        send_kwargs = self.mock_interaction.followup.send.call_args.kwargs
        self.assertNotIn("embed", send_kwargs)
        self.assertEqual(send_kwargs["file"], mock_file)
        self.mock_report_channel.send.assert_called_once()

    async def test_member_select_sends_report_to_report_channel(self):
        db_member = _make_db_member(
            discord_id=self.target_discord_id, nickname="TargetUser"
        )
        self.mock_member_service.get_member_by_discord_id.return_value = db_member
        self.mock_changelog_service.get_changelog_for_member.return_value = []

        with patch("ironforgedbot.commands.admin.view_changelog.discord.File"):
            await self.select_item.callback(self.mock_interaction)

        self.mock_report_channel.send.assert_called_once()
        report_text = self.mock_report_channel.send.call_args.args[0]
        self.assertIn(self.mock_interaction.user.mention, report_text)
        self.assertIn("TargetUser", report_text)
        self.assertIn(f"<@{self.target_discord_id}>", report_text)
        self.assertTrue(report_text.startswith(":scroll:"))

    async def test_member_select_swallows_report_channel_errors(self):
        db_member = _make_db_member(discord_id=self.target_discord_id)
        self.mock_member_service.get_member_by_discord_id.return_value = db_member
        self.mock_changelog_service.get_changelog_for_member.return_value = []
        self.mock_report_channel.send.side_effect = discord.Forbidden(
            Mock(status=403), "missing access"
        )

        with patch("ironforgedbot.commands.admin.view_changelog.discord.File"):
            await self.select_item.callback(self.mock_interaction)

        self.mock_interaction.followup.send.assert_called_once()
        self.mock_report_channel.send.assert_called_once()

    async def test_member_select_file_uses_table_with_required_columns(self):
        db_member = _make_db_member(
            discord_id=self.target_discord_id, nickname="TargetUser"
        )
        self.mock_member_service.get_member_by_discord_id.return_value = db_member

        entry = _make_changelog_entry(
            id=1,
            change_type=ChangeType.NAME_CHANGE,
            previous_value="OldName",
            new_value="NewName",
            comment="Renamed",
        )
        entry.admin_member = None
        self.mock_changelog_service.get_changelog_for_member.return_value = [entry]

        captured = {}

        def _capture_file(fp, filename):
            captured["filename"] = filename
            fp.seek(0)
            captured["body"] = fp.read().decode("utf-8")
            return Mock()

        with patch(
            "ironforgedbot.commands.admin.view_changelog.discord.File",
            side_effect=_capture_file,
        ):
            await self.select_item.callback(self.mock_interaction)

        body = captured["body"]
        self.assertIn("Timestamp", body)
        self.assertIn("Type", body)
        self.assertIn("Previous", body)
        self.assertIn("New", body)
        self.assertIn("Comment", body)
        self.assertIn("Admin", body)
        self.assertIn(CHANGE_TYPE_LABELS[ChangeType.NAME_CHANGE], body)
        self.assertIn("OldName", body)
        self.assertIn("NewName", body)
        self.assertIn("Renamed", body)
        self.assertIn("System", body)
        self.assertIn("# Changelog for TargetUser (last 30 days)", body)
        self.assertFalse(body.startswith("```"))


class TestChangelogSelectViewLifecycle(_Base, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = AsyncMock(spec=discord.TextChannel)
        with patch("discord.ui.View.__init__", return_value=None):
            self.view = ChangelogSelectView(report_channel=self.mock_report_channel)

    async def test_on_timeout_deletes_message(self):
        mock_message = AsyncMock()
        self.view.message = mock_message

        await self.view.on_timeout()

        mock_message.delete.assert_called_once()

    async def test_on_timeout_without_message_does_not_raise(self):
        self.view.message = None

        await self.view.on_timeout()


class TestBuildChangelogTextBody(_Base, unittest.TestCase):
    def test_empty_entries_returns_table_with_header_only(self):
        from ironforgedbot.commands.admin.view_changelog import (
            _build_changelog_text_body,
        )

        body = _build_changelog_text_body([], "TestUser")

        self.assertIn("Timestamp", body)
        self.assertIn("Type", body)
        self.assertNotIn("```", body)

    def test_window_label_appears_in_header(self):
        from ironforgedbot.commands.admin.view_changelog import (
            _build_changelog_text_body,
        )

        body = _build_changelog_text_body([], "TestUser", window_label="last 30 days")

        self.assertIn("# Changelog for TestUser (last 30 days)", body)

    def test_no_window_label_omits_suffix(self):
        from ironforgedbot.commands.admin.view_changelog import (
            _build_changelog_text_body,
        )

        body = _build_changelog_text_body([], "TestUser")

        self.assertIn("# Changelog for TestUser\n", body)
        self.assertNotIn("(last", body)

    def test_admin_falls_back_to_system_when_admin_member_missing(self):
        from ironforgedbot.commands.admin.view_changelog import (
            _build_changelog_text_body,
        )

        entry = _make_changelog_entry(admin_id="admin-uuid")
        entry.admin_member = None

        body = _build_changelog_text_body([entry], "TestUser")

        self.assertIn("System", body)

    def test_admin_uses_nickname_when_admin_member_present(self):
        from ironforgedbot.commands.admin.view_changelog import (
            _build_changelog_text_body,
        )

        entry = _make_changelog_entry(admin_id="admin-uuid")
        entry.admin_member = _make_admin_member(nickname="ModUser")

        body = _build_changelog_text_body([entry], "TestUser")

        self.assertIn("ModUser", body)
