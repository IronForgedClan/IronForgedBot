import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.errors import Forbidden

from ironforgedbot.common.roles import ROLE
from ironforgedbot.events.handlers.nickname_change import NicknameChangeHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.services.member_service import UniqueNicknameViolation
from tests.helpers import create_test_db_member, create_test_member


class TestNicknameChangeHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_nickname_changed_and_has_member_role(self):
        """should_handle returns True when nickname changed and member has Member role."""
        handler = NicknameChangeHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER], "OldNick")
        after = create_test_member("TestUser", [ROLE.MEMBER], "NewNick")
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_nickname_not_changed(self):
        """should_handle returns False when nickname did not change."""
        handler = NicknameChangeHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER], "SameNick")
        after = create_test_member("TestUser", [ROLE.MEMBER], "SameNick")
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_no_member_role(self):
        """should_handle returns False when member doesn't have Member role."""
        handler = NicknameChangeHandler()

        before = create_test_member("TestUser", [], "OldNick")
        after = create_test_member("TestUser", [], "NewNick")
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))


class TestNicknameChangeHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = NicknameChangeHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, old_nick="OldNick", new_nick="NewNick"):
        before = create_test_member("TestUser", [ROLE.MEMBER], old_nick)
        after = create_test_member("TestUser", [ROLE.MEMBER], new_nick)
        after.id = before.id
        after.display_name = new_nick
        before.display_name = old_nick

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)
        report_channel.guild.get_member = Mock(return_value=None)

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch("ironforgedbot.events.handlers.nickname_change.normalize_discord_string")
    async def test_execute_updates_database(self, mock_normalize):
        """Updates member nickname in database."""
        mock_normalize.return_value = "NewNick"

        db_member = create_test_db_member(
            nickname="OldNick", discord_id=12345, id="test-id"
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_nickname = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_nickname.assert_called_once_with("test-id", "NewNick")
        self.assertIn("nickname changed", result.lower())

    @patch("ironforgedbot.events.handlers.nickname_change.normalize_discord_string")
    async def test_execute_no_change_when_already_matches(self, mock_normalize):
        """Returns None when database already has the same nickname."""
        mock_normalize.return_value = "SameNick"

        db_member = create_test_db_member(nickname="SameNick", discord_id=12345)
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)

        context = self._create_context(old_nick="OldNick", new_nick="SameNick")

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_nickname.assert_not_called()
        self.assertIsNone(result)

    @patch("ironforgedbot.events.handlers.nickname_change.normalize_discord_string")
    async def test_execute_member_not_found_rollback(self, mock_normalize):
        """Rolls back nickname when member not found in database."""
        mock_normalize.return_value = "NewNick"
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.edit.assert_called_once()
        self.assertIn("nickname changed", result.lower())
        self.assertIn("rolled back", result.lower())

    @patch("ironforgedbot.events.handlers.nickname_change.normalize_discord_string")
    async def test_execute_nickname_conflict_rollback(self, mock_normalize):
        """Rolls back nickname on conflict."""
        mock_normalize.return_value = "NewNick"

        db_member = create_test_db_member(nickname="OldNick", discord_id=12345)
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_nickname = AsyncMock(
            side_effect=UniqueNicknameViolation("nickname")
        )
        self.mock_service.get_member_by_nickname = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.edit.assert_called_once()
        self.assertIn("nickname changed", result.lower())
        self.assertIn("conflict", result.lower())

    @patch("ironforgedbot.events.handlers.nickname_change.normalize_discord_string")
    async def test_execute_forbidden_rollback_returns_none(self, mock_normalize):
        """Returns None when rollback fails due to permission error."""
        mock_normalize.return_value = "NewNick"
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()
        context.after.edit = AsyncMock(
            side_effect=Forbidden(Mock(), "Missing permissions")
        )

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIsNone(result)
        context.report_channel.send.assert_called_once()


class TestNicknameChangeHandlerRollback(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = NicknameChangeHandler()

    async def test_rollback_restores_previous_nickname(self):
        """_rollback restores the previous nickname."""
        before = create_test_member("TestUser", [ROLE.MEMBER], "OldNick")
        after = create_test_member("TestUser", [ROLE.MEMBER], "NewNick")
        after.id = before.id
        report_channel = AsyncMock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        result = await self.handler._rollback(context, "OldNick")

        self.assertTrue(result)
        after.edit.assert_called_once_with(
            nick="OldNick",
            reason="Nickname conflict in database, rolling back nickname",
        )

    async def test_rollback_returns_false_on_forbidden(self):
        """_rollback returns False when permission denied."""
        before = create_test_member("TestUser", [ROLE.MEMBER], "OldNick")
        after = create_test_member("TestUser", [ROLE.MEMBER], "NewNick")
        after.id = before.id
        after.edit = AsyncMock(side_effect=Forbidden(Mock(), "Missing permissions"))
        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        result = await self.handler._rollback(context, "OldNick")

        self.assertFalse(result)
        report_channel.send.assert_called_once()


class TestNicknameChangeHandlerConflict(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = NicknameChangeHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self):
        before = create_test_member("TestUser", [ROLE.MEMBER], "OldNick")
        after = create_test_member("TestUser", [ROLE.MEMBER], "NewNick")
        after.id = before.id
        before.display_name = "OldNick"
        after.display_name = "NewNick"

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)
        report_channel.guild.get_member = Mock(return_value=None)

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch("ironforgedbot.events.handlers.nickname_change.normalize_discord_string")
    async def test_conflict_with_existing_discord_member(self, mock_normalize):
        """Shows conflicting discord member in conflict message."""
        mock_normalize.return_value = "NewNick"

        db_member = create_test_db_member(nickname="OldNick", discord_id=12345)
        conflicting_db_member = create_test_db_member(
            nickname="NewNick", discord_id=67890, id="conflict-id"
        )
        conflicting_discord_member = create_test_member("ConflictUser", [ROLE.MEMBER])

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_nickname = AsyncMock(
            side_effect=UniqueNicknameViolation("nickname")
        )
        self.mock_service.get_member_by_nickname = AsyncMock(
            return_value=conflicting_db_member
        )

        context = self._create_context()
        context.report_channel.guild.get_member = Mock(
            return_value=conflicting_discord_member
        )

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("nickname changed", result.lower())
        self.assertIn("conflict", result.lower())
        self.assertIn(conflicting_discord_member.mention, result)


class TestNicknameChangeHandlerPriority(unittest.TestCase):
    def test_priority_is_50(self):
        """NicknameChangeHandler has default priority 50."""
        handler = NicknameChangeHandler()
        self.assertEqual(handler.priority, 50)

    def test_name_property(self):
        """Handler name is NicknameChange."""
        handler = NicknameChangeHandler()
        self.assertEqual(handler.name, "NicknameChange")
