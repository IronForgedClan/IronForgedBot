import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.events.handlers.update_member_role import UpdateMemberRoleHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import create_test_db_member, create_test_member


class TestUpdateMemberRoleHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_roles_changed_and_has_member(self):
        """should_handle returns True when roles changed and has Member role."""
        handler = UpdateMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, ROLE.LEADERSHIP])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_roles_not_changed(self):
        """should_handle returns False when no roles changed."""
        handler = UpdateMemberRoleHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER])
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
    @patch("ironforgedbot.events.handlers.update_member_role.has_booster_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_prospect_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_blacklisted_role")
    @patch("ironforgedbot.events.handlers.update_member_role.is_member_banned_by_role")
    async def test_execute_updates_role(
        self,
        mock_banned,
        mock_blacklisted,
        mock_prospect,
        mock_booster,
        mock_get_role,
    ):
        """Updates member role when highest privilege role changes."""
        mock_get_role.return_value = ROLE.LEADERSHIP
        mock_booster.return_value = False
        mock_prospect.return_value = False
        mock_blacklisted.return_value = False
        mock_banned.return_value = False

        db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            id="test-id",
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        db_member.role = ROLE.MEMBER
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_role = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_role.assert_called_once()
        self.assertIn("role", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    @patch("ironforgedbot.events.handlers.update_member_role.has_booster_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_prospect_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_blacklisted_role")
    @patch("ironforgedbot.events.handlers.update_member_role.is_member_banned_by_role")
    async def test_execute_updates_booster_flag(
        self,
        mock_banned,
        mock_blacklisted,
        mock_prospect,
        mock_booster,
        mock_get_role,
    ):
        """Updates is_booster flag when booster status changes."""
        mock_get_role.return_value = None
        mock_booster.return_value = True
        mock_prospect.return_value = False
        mock_blacklisted.return_value = False
        mock_banned.return_value = False

        db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            id="test-id",
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        db_member.role = None
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_called_once()
        call_kwargs = self.mock_service.update_member_flags.call_args[1]
        self.assertTrue(call_kwargs["is_booster"])
        self.assertIn("booster", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    @patch("ironforgedbot.events.handlers.update_member_role.has_booster_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_prospect_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_blacklisted_role")
    @patch("ironforgedbot.events.handlers.update_member_role.is_member_banned_by_role")
    async def test_execute_updates_prospect_flag(
        self,
        mock_banned,
        mock_blacklisted,
        mock_prospect,
        mock_booster,
        mock_get_role,
    ):
        """Updates is_prospect flag when prospect status changes."""
        mock_get_role.return_value = None
        mock_booster.return_value = False
        mock_prospect.return_value = True
        mock_blacklisted.return_value = False
        mock_banned.return_value = False

        db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            id="test-id",
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        db_member.role = None
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_called_once()
        call_kwargs = self.mock_service.update_member_flags.call_args[1]
        self.assertTrue(call_kwargs["is_prospect"])
        self.assertIn("prospect", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    @patch("ironforgedbot.events.handlers.update_member_role.has_booster_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_prospect_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_blacklisted_role")
    @patch("ironforgedbot.events.handlers.update_member_role.is_member_banned_by_role")
    async def test_execute_updates_blacklisted_flag(
        self,
        mock_banned,
        mock_blacklisted,
        mock_prospect,
        mock_booster,
        mock_get_role,
    ):
        """Updates is_blacklisted flag when blacklisted status changes."""
        mock_get_role.return_value = None
        mock_booster.return_value = False
        mock_prospect.return_value = False
        mock_blacklisted.return_value = True
        mock_banned.return_value = False

        db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            id="test-id",
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        db_member.role = None
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_called_once()
        call_kwargs = self.mock_service.update_member_flags.call_args[1]
        self.assertTrue(call_kwargs["is_blacklisted"])
        self.assertIn("blacklisted", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    @patch("ironforgedbot.events.handlers.update_member_role.has_booster_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_prospect_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_blacklisted_role")
    @patch("ironforgedbot.events.handlers.update_member_role.is_member_banned_by_role")
    async def test_execute_updates_banned_flag(
        self,
        mock_banned,
        mock_blacklisted,
        mock_prospect,
        mock_booster,
        mock_get_role,
    ):
        """Updates is_banned flag when banned status changes."""
        mock_get_role.return_value = None
        mock_booster.return_value = False
        mock_prospect.return_value = False
        mock_blacklisted.return_value = False
        mock_banned.return_value = True

        db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            id="test-id",
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        db_member.role = None
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.update_member_flags = AsyncMock()

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.update_member_flags.assert_called_once()
        call_kwargs = self.mock_service.update_member_flags.call_args[1]
        self.assertTrue(call_kwargs["is_banned"])
        self.assertIn("banned", result.lower())

    @patch(
        "ironforgedbot.events.handlers.update_member_role.get_highest_privilage_role_from_member"
    )
    @patch("ironforgedbot.events.handlers.update_member_role.has_booster_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_prospect_role")
    @patch("ironforgedbot.events.handlers.update_member_role.has_blacklisted_role")
    @patch("ironforgedbot.events.handlers.update_member_role.is_member_banned_by_role")
    async def test_execute_no_change_returns_none(
        self,
        mock_banned,
        mock_blacklisted,
        mock_prospect,
        mock_booster,
        mock_get_role,
    ):
        """Returns None when no changes detected."""
        mock_get_role.return_value = ROLE.MEMBER
        mock_booster.return_value = False
        mock_prospect.return_value = False
        mock_blacklisted.return_value = False
        mock_banned.return_value = False

        db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            id="test-id",
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        db_member.role = ROLE.MEMBER
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_role.assert_not_called()
        self.mock_service.update_member_flags.assert_not_called()
        self.assertIsNone(result)

    async def test_execute_member_not_found_returns_none(self):
        """Returns None when member not found in database."""
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIsNone(result)


class TestUpdateMemberRoleHandlerPriority(unittest.TestCase):
    def test_priority_is_40(self):
        """UpdateMemberRoleHandler has priority 40."""
        handler = UpdateMemberRoleHandler()
        self.assertEqual(handler.priority, 40)

    def test_name_property(self):
        """Handler name is UpdateMemberRole."""
        handler = UpdateMemberRoleHandler()
        self.assertEqual(handler.name, "UpdateMemberRole")
