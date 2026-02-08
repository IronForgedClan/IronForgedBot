import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE, PROSPECT_ROLE_NAME
from ironforgedbot.events.handlers.add_prospect_role import AddProspectRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import create_test_db_member, create_test_member


class TestAddProspectRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_prospect_role_added(self):
        """should_handle returns True when Prospect role is added."""
        handler = AddProspectRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, PROSPECT_ROLE_NAME])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_prospect_role_not_added(self):
        """should_handle returns False when Prospect role was not added."""
        handler = AddProspectRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, PROSPECT_ROLE_NAME])
        after = create_test_member("TestUser", [ROLE.MEMBER, PROSPECT_ROLE_NAME])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_other_role_added(self):
        """should_handle returns False when a different role is added."""
        handler = AddProspectRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))


class TestAddProspectRoleHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AddProspectRoleHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None):
        before_roles = before_roles or [ROLE.MEMBER]
        after_roles = after_roles or [ROLE.MEMBER, PROSPECT_ROLE_NAME]

        before = create_test_member("TestUser", before_roles, "TestNick")
        after = create_test_member("TestUser", after_roles, "TestNick")
        after.id = before.id
        after.display_name = "TestNick"

        # Create a mock message that can be edited
        mock_message = AsyncMock()
        mock_message.edit = AsyncMock()

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock(return_value=mock_message)
        report_channel.guild = Mock(spec=discord.Guild)
        report_channel.guild.roles = []

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_updates_prospect_flag(
        self, mock_check_role, mock_get_role
    ):
        """Updates is_prospect flag in database."""
        mock_check_role.return_value = False
        mock_get_role.return_value = Mock(spec=discord.Role)

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id"
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        self.mock_service.update_member_flags.assert_called_once_with(
            "test-id", is_prospect=True
        )

    @patch("ironforgedbot.events.handlers.add_prospect_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_removes_applicant_role(
        self, mock_check_role, mock_get_role, mock_emitter
    ):
        """Removes Applicant role when present."""
        mock_check_role.side_effect = lambda m, r: r == ROLE.APPLICANT
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(
            after_roles=[ROLE.MEMBER, PROSPECT_ROLE_NAME, ROLE.APPLICANT]
        )

        await self.handler._execute(context, self.mock_session, self.mock_service)

        context.after.remove_roles.assert_called()
        mock_emitter.suppress_next_for.assert_called()

    @patch("ironforgedbot.events.handlers.add_prospect_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_removes_guest_role(
        self, mock_check_role, mock_get_role, mock_emitter
    ):
        """Removes Guest role when present."""
        mock_check_role.side_effect = lambda m, r: r == ROLE.GUEST
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(
            after_roles=[ROLE.MEMBER, PROSPECT_ROLE_NAME, ROLE.GUEST]
        )

        await self.handler._execute(context, self.mock_session, self.mock_service)

        context.after.remove_roles.assert_called()
        mock_emitter.suppress_next_for.assert_called()

    @patch("ironforgedbot.events.handlers.add_prospect_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_adds_member_role_if_missing(
        self, mock_check_role, mock_get_role, mock_emitter
    ):
        """Adds Member role if not present."""
        mock_check_role.side_effect = lambda m, r: r != ROLE.MEMBER
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context(after_roles=[PROSPECT_ROLE_NAME])

        await self.handler._execute(context, self.mock_session, self.mock_service)

        context.after.add_roles.assert_called()
        mock_emitter.suppress_next_for.assert_called()

    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_sends_initial_message(
        self, mock_check_role, mock_get_role
    ):
        """Sends initial message when processing starts."""
        mock_check_role.return_value = False
        mock_get_role.return_value = Mock(spec=discord.Role)

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        context.report_channel.send.assert_called()

    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_raises_when_role_not_found(
        self, mock_check_role, mock_get_role
    ):
        """Raises ValueError when required role cannot be found."""
        mock_check_role.side_effect = lambda m, r: r == ROLE.APPLICANT
        mock_get_role.return_value = None

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        with self.assertRaises(ValueError):
            await self.handler._execute(context, self.mock_session, self.mock_service)

    @patch("ironforgedbot.events.handlers.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.events.handlers.add_prospect_role.check_member_has_role")
    async def test_execute_no_db_member_still_processes(
        self, mock_check_role, mock_get_role
    ):
        """Processes role changes even when no db member found."""
        mock_check_role.return_value = False
        mock_get_role.return_value = Mock(spec=discord.Role)

        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_not_called()
        self.assertIsNone(result)


class TestAddProspectRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_20(self):
        """AddProspectRoleHandler has priority 20."""
        handler = AddProspectRoleHandler()
        self.assertEqual(handler.priority, 20)

    def test_name_property(self):
        """Handler name is AddProspectRole."""
        handler = AddProspectRoleHandler()
        self.assertEqual(handler.name, "AddProspectRole")
