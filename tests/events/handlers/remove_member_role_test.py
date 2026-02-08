import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.errors import Forbidden

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.events.handlers.remove_member_role import RemoveMemberRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import create_test_db_member, create_test_member


class TestRemoveMemberRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_member_role_removed(self):
        """should_handle returns True when Member role is removed."""
        handler = RemoveMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_member_role_not_removed(self):
        """should_handle returns False when Member role was not removed."""
        handler = RemoveMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_other_role_removed(self):
        """should_handle returns False when a different role is removed."""
        handler = RemoveMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))


class TestRemoveMemberRoleHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = RemoveMemberRoleHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None, nick="TestUser"):
        before_roles = before_roles or [ROLE.MEMBER]
        after_roles = after_roles or []

        before = create_test_member("TestUser", before_roles, nick)
        after = create_test_member("TestUser", after_roles, nick)
        after.id = before.id
        after.display_name = nick

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch("ironforgedbot.events.handlers.remove_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_removes_monitored_roles(self, mock_get_role, mock_emitter):
        """Removes all monitored roles from the member."""
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        db_member = create_test_db_member(nickname="TestUser", discord_id=12345)
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.disable_member = AsyncMock()

        context = self._create_context(after_roles=[RANK.IRON, ROLE.LEADERSHIP])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_called_once()
        mock_emitter.suppress_next_for.assert_called_once()
        self.assertIn("disabled", result.lower())

    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_disables_member_in_database(self, mock_get_role):
        """Disables the member in the database."""
        mock_get_role.return_value = None

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.disable_member = AsyncMock()

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        self.mock_service.disable_member.assert_called_once_with("test-id")

    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_member_not_found_returns_warning(self, mock_get_role):
        """Returns warning when member not found in database."""
        mock_get_role.return_value = None
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("warning", result.lower())
        self.assertIn("cannot be found", result.lower())

    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_forbidden_error_returns_warning(self, mock_get_role):
        """Returns warning when bot lacks permission to remove roles."""
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        context = self._create_context(after_roles=[RANK.IRON])
        context.after.remove_roles = AsyncMock(
            side_effect=Forbidden(Mock(), "Missing permissions")
        )

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("permission", result.lower())

    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_role_not_found_raises(self, mock_get_role):
        """Raises ValueError when role cannot be found."""
        mock_get_role.return_value = None

        context = self._create_context(after_roles=[RANK.IRON])

        with self.assertRaises(ValueError):
            await self.handler._execute(context, self.mock_session, self.mock_service)

    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_no_roles_to_remove(self, mock_get_role):
        """Handles case with no monitored roles to remove."""
        mock_get_role.return_value = None

        db_member = create_test_db_member(nickname="TestUser", discord_id=12345)
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.disable_member = AsyncMock()

        context = self._create_context(after_roles=[])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_not_called()
        self.assertIn("disabled", result.lower())

    @patch("ironforgedbot.events.handlers.remove_member_role.get_discord_role")
    async def test_execute_lists_removed_roles_in_response(self, mock_get_role):
        """Response includes list of removed roles."""
        mock_role = Mock(spec=discord.Role)
        mock_role.name = RANK.IRON
        mock_get_role.return_value = mock_role

        db_member = create_test_db_member(nickname="TestUser", discord_id=12345)
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.disable_member = AsyncMock()

        context = self._create_context(after_roles=[RANK.IRON])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn(RANK.IRON, result)


class TestRemoveMemberRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_10(self):
        """RemoveMemberRoleHandler has priority 10 (runs early)."""
        handler = RemoveMemberRoleHandler()
        self.assertEqual(handler.priority, 10)

    def test_name_property(self):
        """Handler name is RemoveMemberRole."""
        handler = RemoveMemberRoleHandler()
        self.assertEqual(handler.name, "RemoveMemberRole")
