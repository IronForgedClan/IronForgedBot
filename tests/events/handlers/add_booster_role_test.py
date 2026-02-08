import unittest
from unittest.mock import AsyncMock, Mock

import discord

from ironforgedbot.common.roles import ROLE, BOOSTER_ROLE_NAME
from ironforgedbot.events.handlers.add_booster_role import AddBoosterRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import create_test_db_member, create_test_member


class TestAddBoosterRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_booster_role_added(self):
        """should_handle returns True when Server Booster role is added."""
        handler = AddBoosterRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, BOOSTER_ROLE_NAME])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_booster_role_not_added(self):
        """should_handle returns False when Server Booster role was not added."""
        handler = AddBoosterRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, BOOSTER_ROLE_NAME])
        after = create_test_member("TestUser", [ROLE.MEMBER, BOOSTER_ROLE_NAME])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_other_role_added(self):
        """should_handle returns False when a different role is added."""
        handler = AddBoosterRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))


class TestAddBoosterRoleHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AddBoosterRoleHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None):
        before_roles = before_roles or [ROLE.MEMBER]
        after_roles = after_roles or [ROLE.MEMBER, BOOSTER_ROLE_NAME]

        before = create_test_member("TestUser", before_roles, "TestNick")
        after = create_test_member("TestUser", after_roles, "TestNick")
        after.id = before.id
        after.display_name = "TestNick"

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)
        report_channel.guild.roles = []

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    async def test_execute_updates_booster_flag(self):
        """Updates is_booster flag to True in database."""
        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        self.mock_service.update_member_flags.assert_called_once_with(
            "test-id", is_booster=True
        )

    async def test_execute_returns_message(self):
        """Returns message when Server Booster role is added."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("**Booster:**", result)
        self.assertIn("added", result)

    async def test_execute_no_db_member_still_returns_message(self):
        """Returns message even when no db member found."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_not_called()
        self.assertIsNotNone(result)


class TestAddBoosterRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_20(self):
        """AddBoosterRoleHandler has priority 20."""
        handler = AddBoosterRoleHandler()
        self.assertEqual(handler.priority, 20)

    def test_name_property(self):
        """Handler name is AddBoosterRole."""
        handler = AddBoosterRoleHandler()
        self.assertEqual(handler.name, "AddBoosterRole")
