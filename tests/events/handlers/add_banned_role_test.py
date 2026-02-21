import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.errors import Forbidden

from ironforgedbot.common.roles import ROLE, BANNED_ROLE_NAME
from ironforgedbot.events.handlers.add_banned_role import AddBannedRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import (
    create_mock_discord_role,
    create_test_db_member,
    create_test_member,
)


class TestAddBannedRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_banned_role_added(self):
        """should_handle returns True when Banned (Slag) role is added."""
        handler = AddBannedRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, BANNED_ROLE_NAME])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_banned_role_not_added(self):
        """should_handle returns False when Banned role was not added."""
        handler = AddBannedRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, BANNED_ROLE_NAME])
        after = create_test_member("TestUser", [ROLE.MEMBER, BANNED_ROLE_NAME])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_other_role_added(self):
        """should_handle returns False when a different role is added."""
        handler = AddBannedRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))


class TestAddBannedRoleHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AddBannedRoleHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None, extra_roles=None):
        before_roles = before_roles or [ROLE.MEMBER]
        after_roles = after_roles or [ROLE.MEMBER, BANNED_ROLE_NAME]

        before = create_test_member("TestUser", before_roles, "TestNick")
        after = create_test_member("TestUser", after_roles, "TestNick")
        after.id = before.id
        after.display_name = "TestNick"

        # Add extra unmonitored roles if specified
        if extra_roles:
            for role_name in extra_roles:
                role = create_mock_discord_role(role_name)
                after.roles.append(role)

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)
        report_channel.guild.roles = []

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    async def test_execute_updates_banned_flag(self):
        """Updates is_banned flag in database."""
        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        self.mock_service.update_member_flags.assert_called_once_with(
            "test-id", is_banned=True
        )

    async def test_execute_removes_unmonitored_roles(self):
        """Removes unmonitored roles from member."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(extra_roles=["UnmonitoredRole", "AnotherRole"])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_called()
        self.assertIn("banned", result.lower())

    @patch("ironforgedbot.events.handlers.add_banned_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_banned_role.get_discord_role")
    async def test_execute_removes_member_role(self, mock_get_role, mock_emitter):
        """Removes Member role to trigger cascade."""
        mock_member_role = create_mock_discord_role(ROLE.MEMBER)
        mock_get_role.return_value = mock_member_role

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()
        # Simulate Member role is present
        context.after.roles = [mock_member_role]

        await self.handler._execute(context, self.mock_session, self.mock_service)

        context.after.remove_roles.assert_called()
        context.report_channel.send.assert_called()

    async def test_execute_forbidden_returns_warning(self):
        """Returns warning when bot lacks permission."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(extra_roles=["UnmonitoredRole"])
        context.after.remove_roles = AsyncMock(
            side_effect=Forbidden(Mock(), "Missing permissions")
        )

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("permission", result.lower())

    async def test_execute_generic_error_returns_warning(self):
        """Returns warning on generic error."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(extra_roles=["UnmonitoredRole"])
        context.after.remove_roles = AsyncMock(
            side_effect=RuntimeError("Unknown error")
        )

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("went wrong", result.lower())

    async def test_execute_no_db_member_still_processes(self):
        """Processes role removal even when no db member found."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_not_called()
        self.assertIn("banned", result.lower())

    async def test_execute_lists_removed_roles(self):
        """Response includes list of removed unmonitored roles."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(extra_roles=["CustomRole"])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("CustomRole", result)


class TestAddBannedRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_20(self):
        """AddBannedRoleHandler has priority 20."""
        handler = AddBannedRoleHandler()
        self.assertEqual(handler.priority, 20)

    def test_name_property(self):
        """Handler name is AddBannedRole."""
        handler = AddBannedRoleHandler()
        self.assertEqual(handler.name, "AddBannedRole")
