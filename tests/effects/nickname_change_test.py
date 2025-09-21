import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.errors import Forbidden

from ironforgedbot.common.roles import ROLE
from ironforgedbot.effects.nickname_change import _rollback, nickname_change
from ironforgedbot.services.member_service import UniqueNicknameViolation
from tests.helpers import create_test_member


class NicknameChangeTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_report_channel.guild = self.mock_guild
        self.before_member = create_test_member("OldNick", [ROLE.MEMBER], "OldNick")
        self.before_member.id = 123456789
        self.before_member.display_name = "OldNick"
        self.after_member = create_test_member("NewNick", [ROLE.MEMBER], "NewNick")
        self.after_member.id = 123456789
        self.after_member.display_name = "NewNick"
        self.after_member.edit = AsyncMock()

    async def test_rollback_successfully_reverts_nickname(self):
        result = await _rollback(self.mock_report_channel, self.after_member, "OldNick")

        self.assertTrue(result)
        self.after_member.edit.assert_called_once_with(
            nick="OldNick",
            reason="Nickname conflict in database, rolling back nickname",
        )

    async def test_rollback_handles_forbidden_error(self):
        self.after_member.edit.side_effect = Forbidden(Mock(), "test")

        result = await _rollback(self.mock_report_channel, self.after_member, "OldNick")

        self.assertFalse(result)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("lacks permission", call_args)

    async def test_ignores_non_member_role_changes(self):
        non_member = create_test_member("Test", [ROLE.APPLICANT], "Test")
        non_member.id = 123456789

        await nickname_change(self.mock_report_channel, self.before_member, non_member)

        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_updates_nickname_successfully(
        self, mock_db, mock_normalize, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_normalize.return_value = "NewNick"
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.nickname = "OldNick"
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_nickname = AsyncMock()

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_service.change_nickname.assert_called_once_with(mock_member.id, "NewNick")
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("Database updated", call_args)

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change._rollback")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_handles_member_not_found_in_database(
        self, mock_db, mock_rollback, mock_normalize, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_normalize.return_value = "NewNick"
        mock_rollback.return_value = True
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.after_member, "OldNick"
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("Member not found in database", call_args)

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change._rollback")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_handles_member_not_found_rollback_failure(
        self, mock_db, mock_rollback, mock_normalize, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_normalize.return_value = "NewNick"
        mock_rollback.return_value = False
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.after_member, "OldNick"
        )
        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_ignores_when_nickname_unchanged(
        self, mock_db, mock_normalize, mock_time
    ):
        mock_normalize.return_value = "SameName"
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.nickname = "SameName"
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_service.change_nickname.assert_not_called()
        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change._rollback")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_handles_nickname_conflict_with_discord_member(
        self, mock_db, mock_rollback, mock_normalize, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_normalize.return_value = "ConflictName"
        mock_rollback.return_value = True
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.nickname = "OldNick"
        mock_conflicting_db_member = Mock()
        mock_conflicting_db_member.id = 999
        mock_conflicting_db_member.discord_id = 987654321
        mock_conflicting_discord_member = Mock()
        mock_conflicting_discord_member.id = 987654321
        mock_conflicting_discord_member.mention = "<@987654321>"

        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_nickname = AsyncMock(side_effect=UniqueNicknameViolation())
        mock_service.get_member_by_nickname = AsyncMock(
            return_value=mock_conflicting_db_member
        )
        self.mock_guild.get_member.return_value = mock_conflicting_discord_member

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.after_member, "OldNick"
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("nickname conflict", call_args)
        self.assertIn("987654321", call_args)

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change._rollback")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_handles_nickname_conflict_without_discord_member(
        self, mock_db, mock_rollback, mock_normalize, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_normalize.return_value = "ConflictName"
        mock_rollback.return_value = True
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.nickname = "OldNick"
        mock_conflicting_db_member = Mock()
        mock_conflicting_db_member.id = 999
        mock_conflicting_db_member.discord_id = 987654321

        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_nickname = AsyncMock(side_effect=UniqueNicknameViolation())
        mock_service.get_member_by_nickname = AsyncMock(
            return_value=mock_conflicting_db_member
        )
        self.mock_guild.get_member.return_value = None

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.after_member, "OldNick"
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("nickname conflict", call_args)
        self.assertNotIn("987654321", call_args)

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change._rollback")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_handles_conflict_with_missing_conflicting_member(
        self, mock_db, mock_rollback, mock_normalize, mock_time
    ):
        mock_normalize.return_value = "ConflictName"
        mock_rollback.return_value = True
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.nickname = "OldNick"

        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_nickname = AsyncMock(side_effect=UniqueNicknameViolation())
        mock_service.get_member_by_nickname = AsyncMock(return_value=None)

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.after_member, "OldNick"
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("error occured getting", call_args)

    @patch("ironforgedbot.effects.nickname_change.time")
    @patch("ironforgedbot.effects.nickname_change.normalize_discord_string")
    @patch("ironforgedbot.effects.nickname_change._rollback")
    @patch("ironforgedbot.effects.nickname_change.db")
    async def test_handles_conflict_rollback_failure(
        self, mock_db, mock_rollback, mock_normalize, mock_time
    ):
        mock_normalize.return_value = "ConflictName"
        mock_rollback.return_value = False
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.nickname = "OldNick"

        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_nickname = AsyncMock(side_effect=UniqueNicknameViolation())
        mock_service.get_member_by_nickname = AsyncMock(return_value=None)

        with patch(
            "ironforgedbot.effects.nickname_change.MemberService",
            return_value=mock_service,
        ):
            await nickname_change(
                self.mock_report_channel, self.before_member, self.after_member
            )

        mock_rollback.assert_called_once()
        self.mock_report_channel.send.assert_not_called()
