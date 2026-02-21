import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.events.handlers.update_member_role import UpdateMemberRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import create_test_db_member, create_test_member


class TestUpdateMemberRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_role_added_and_has_member(self):
        """should_handle returns True when a ROLE is added and has Member role."""
        handler = UpdateMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_role_not_added(self):
        """should_handle returns False when no ROLE was added."""
        handler = UpdateMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_no_member_role(self):
        """should_handle returns False when member doesn't have Member role."""
        handler = UpdateMemberRoleHandler()

        before = create_test_member("TestUser", [])
        after = create_test_member("TestUser", [ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_true_when_role_removed(self):
        """should_handle returns True when a ROLE is removed and has Member role."""
        handler = UpdateMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_true_for_various_roles(self):
        """should_handle returns True for various ROLE values being added."""
        handler = UpdateMemberRoleHandler()

        for role in [ROLE.MODERATOR, ROLE.STAFF, ROLE.BRIGADIER, ROLE.ADMIRAL]:
            before = create_test_member("TestUser", [ROLE.MEMBER])
            after = create_test_member("TestUser", [ROLE.MEMBER, role])
            after.id = before.id
            report_channel = Mock(spec=discord.TextChannel)

            context = MemberUpdateContext(
                before=before, after=after, report_channel=report_channel
            )

            self.assertTrue(handler.should_handle(context), f"Failed for role {role}")


class TestUpdateMemberRoleHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = UpdateMemberRoleHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None):
        before_roles = before_roles or [ROLE.MEMBER]
        after_roles = after_roles or [ROLE.MEMBER, ROLE.LEADERSHIP]

        before = create_test_member("TestUser", before_roles, "TestNick")
        after = create_test_member("TestUser", after_roles, "TestNick")
        after.id = before.id
        after.display_name = "TestNick"

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    async def test_execute_updates_role(self, mock_get_role):
        """Updates member role in database when role changed."""
        mock_get_role.return_value = ROLE.LEADERSHIP

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        db_member.role = ROLE.MEMBER
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_role = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_role.assert_called_once()
        self.assertIn("role changed", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    async def test_execute_no_change_returns_none(self, mock_get_role):
        """Returns None when role is already the same in database."""
        mock_get_role.return_value = ROLE.MEMBER

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        db_member.role = ROLE.MEMBER
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_role.assert_not_called()
        self.assertIsNone(result)

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    async def test_execute_role_not_determined_returns_warning(self, mock_get_role):
        """Returns warning when role cannot be determined."""
        mock_get_role.return_value = None

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("could not be determined", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    async def test_execute_member_not_found_returns_warning(self, mock_get_role):
        """Returns warning when member not found in database."""
        mock_get_role.return_value = ROLE.LEADERSHIP
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("not found", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    async def test_execute_shows_previous_and_new_role(self, mock_get_role):
        """Response shows previous and new role."""
        mock_get_role.return_value = ROLE.ADMIRAL

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        db_member.role = ROLE.MODERATOR
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_role = AsyncMock()

        context = self._create_context(after_roles=[ROLE.MEMBER, ROLE.ADMIRAL])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn(ROLE.MODERATOR, result)
        self.assertIn(str(ROLE.ADMIRAL), result)


class TestUpdateMemberRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_40(self):
        """UpdateMemberRoleHandler has priority 40."""
        handler = UpdateMemberRoleHandler()
        self.assertEqual(handler.priority, 40)

    def test_name_property(self):
        """Handler name is UpdateMemberRole."""
        handler = UpdateMemberRoleHandler()
        self.assertEqual(handler.name, "UpdateMemberRole")
