import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.events.handlers.add_member_role import AddMemberRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.services.member_service import (
    MemberServiceReactivateResponse,
    UniqueNicknameViolation,
)
from tests.helpers import (
    create_mock_discord_role,
    create_test_db_member,
    create_test_member,
)


class TestAddMemberRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_member_role_added(self):
        """should_handle returns True when Member role is added."""
        handler = AddMemberRoleHandler()

        before = create_test_member("TestUser", [])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_member_role_not_added(self):
        """should_handle returns False when Member role was not added."""
        handler = AddMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_other_role_added(self):
        """should_handle returns False when a different role is added."""
        handler = AddMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))


class TestAddMemberRoleHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AddMemberRoleHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None, nick="TestUser"):
        before_roles = before_roles or []
        after_roles = after_roles or [ROLE.MEMBER]

        before = create_test_member("TestUser", before_roles, nick)
        after = create_test_member("TestUser", after_roles, nick)
        after.id = before.id
        after.display_name = nick

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)
        report_channel.guild.get_member_named = Mock(return_value=None)

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    async def test_execute_creates_new_member(self, mock_get_rank):
        """New member is created when no existing member found."""
        mock_get_rank.return_value = RANK.IRON
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        new_member = create_test_db_member(nickname="TestUser", discord_id=12345)
        self.mock_service.create_member = AsyncMock(return_value=new_member)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.create_member.assert_called_once()
        self.assertIn("new member", result.lower())

    @patch("ironforgedbot.events.handlers.add_member_role.find_emoji")
    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    async def test_execute_reactivates_inactive_member(self, mock_get_rank, mock_emoji):
        """Inactive member is reactivated when found."""
        mock_get_rank.return_value = RANK.IRON
        mock_emoji.return_value = ""

        inactive_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, active=False
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(
            return_value=inactive_member
        )

        reactivate_response = Mock(spec=MemberServiceReactivateResponse)
        reactivate_response.new_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, active=True
        )
        reactivate_response.previous_nick = "OldNick"
        reactivate_response.previous_join_date = datetime(
            2024, 1, 1, tzinfo=timezone.utc
        )
        reactivate_response.approximate_leave_date = datetime(
            2024, 6, 1, tzinfo=timezone.utc
        )
        reactivate_response.previous_rank = RANK.IRON
        reactivate_response.previous_ingot_qty = 1000
        reactivate_response.ingots_reset = False
        self.mock_service.reactivate_member = AsyncMock(
            return_value=reactivate_response
        )

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.reactivate_member.assert_called_once()
        # Result is None because embed is sent directly
        self.assertIsNone(result)

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.events.handlers.add_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_member_role.get_discord_role")
    async def test_execute_already_active_member_rollback(
        self, mock_get_role, mock_emitter, mock_get_rank
    ):
        """Already active member triggers rollback and warning."""
        mock_get_rank.return_value = RANK.IRON

        active_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, active=True
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(
            return_value=active_member
        )

        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_called_once()
        mock_emitter.suppress_next_for.assert_called_once()
        self.assertIn("warning", result.lower())
        self.assertIn("already registered", result.lower())

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.events.handlers.add_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_member_role.get_discord_role")
    async def test_execute_nickname_conflict_on_create(
        self, mock_get_role, mock_emitter, mock_get_rank
    ):
        """Nickname conflict during create triggers rollback."""
        mock_get_rank.return_value = RANK.IRON
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        self.mock_service.create_member = AsyncMock(
            side_effect=UniqueNicknameViolation("nickname")
        )
        self.mock_service.get_member_by_nickname = AsyncMock(return_value=None)

        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_called_once()
        mock_emitter.suppress_next_for.assert_called_once()
        self.assertIn("nickname conflict", result.lower())

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.events.handlers.add_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_member_role.get_discord_role")
    async def test_execute_nickname_conflict_on_reactivate(
        self, mock_get_role, mock_emitter, mock_get_rank
    ):
        """Nickname conflict during reactivate triggers rollback."""
        mock_get_rank.return_value = RANK.IRON

        inactive_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, active=False
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(
            return_value=inactive_member
        )
        self.mock_service.reactivate_member = AsyncMock(
            side_effect=UniqueNicknameViolation("nickname")
        )
        self.mock_service.get_member_by_nickname = AsyncMock(return_value=None)

        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_called_once()
        mock_emitter.suppress_next_for.assert_called_once()
        self.assertIn("nickname conflict", result.lower())

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.events.handlers.add_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_member_role.get_discord_role")
    async def test_execute_member_creation_fails(
        self, mock_get_role, mock_emitter, mock_get_rank
    ):
        """Failed member creation triggers rollback."""
        mock_get_rank.return_value = RANK.IRON
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        self.mock_service.create_member = AsyncMock(return_value=None)

        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        context.after.remove_roles.assert_called_once()
        self.assertIn("error", result.lower())

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    async def test_execute_god_alignment_maps_to_god_rank(self, mock_get_rank):
        """God alignment ranks are mapped to GOD rank."""
        from ironforgedbot.common.ranks import GOD_ALIGNMENT

        mock_get_rank.return_value = GOD_ALIGNMENT.ZAMORAK
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        new_member = create_test_db_member(nickname="TestUser", discord_id=12345)
        self.mock_service.create_member = AsyncMock(return_value=new_member)

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        call_args = self.mock_service.create_member.call_args
        self.assertEqual(call_args[0][2], RANK.GOD)

    @patch("ironforgedbot.events.handlers.add_member_role.get_rank_from_member")
    async def test_execute_no_rank_defaults_to_iron(self, mock_get_rank):
        """No detected rank defaults to Iron."""
        mock_get_rank.return_value = None
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        new_member = create_test_db_member(nickname="TestUser", discord_id=12345)
        self.mock_service.create_member = AsyncMock(return_value=new_member)

        context = self._create_context()

        await self.handler._execute(context, self.mock_session, self.mock_service)

        call_args = self.mock_service.create_member.call_args
        self.assertEqual(call_args[0][2], RANK.IRON)


class TestAddMemberRoleHandlerRollback(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = AddMemberRoleHandler()

    @patch("ironforgedbot.events.handlers.add_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_member_role.get_discord_role")
    async def test_rollback_removes_member_role(self, mock_get_role, mock_emitter):
        """_rollback removes the Member role."""
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        before = create_test_member("TestUser", [])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.guild = Mock(spec=discord.Guild)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        await self.handler._rollback(context)

        after.remove_roles.assert_called_once_with(
            mock_role, reason="Error saving member to database"
        )
        mock_emitter.suppress_next_for.assert_called_once_with(context.discord_id)

    @patch("ironforgedbot.events.handlers.add_member_role.member_update_emitter")
    @patch("ironforgedbot.events.handlers.add_member_role.get_discord_role")
    async def test_on_error_calls_rollback(self, mock_get_role, mock_emitter):
        """_on_error calls _rollback before returning error message."""
        mock_role = Mock(spec=discord.Role)
        mock_get_role.return_value = mock_role

        before = create_test_member("TestUser", [])
        after = create_test_member("TestUser", [ROLE.MEMBER])
        after.id = before.id
        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.guild = Mock(spec=discord.Guild)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        error = ValueError("Test error")
        result = await self.handler._on_error(context, error)

        after.remove_roles.assert_called_once()
        self.assertIn("AddMemberRole", result)


class TestAddMemberRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_10(self):
        """AddMemberRoleHandler has priority 10 (runs early)."""
        handler = AddMemberRoleHandler()
        self.assertEqual(handler.priority, 10)

    def test_name_property(self):
        """Handler name is AddMemberRole."""
        handler = AddMemberRoleHandler()
        self.assertEqual(handler.name, "AddMemberRole")
