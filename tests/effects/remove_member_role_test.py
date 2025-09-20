import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.errors import Forbidden

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.effects.remove_member_role import remove_member_role
from tests.helpers import create_test_member


class RemoveMemberRoleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_report_channel.guild = self.mock_guild
        self.member = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON], "TestUser")
        self.member.id = 123456789
        self.member.display_name = "TestUser"
        self.member.mention = "<@123456789>"
        self.member.remove_roles = AsyncMock()

    @patch("ironforgedbot.effects.remove_member_role.time")
    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    @patch("ironforgedbot.effects.remove_member_role.db")
    async def test_removes_roles_and_disables_member(self, mock_db, mock_is_banned, mock_get_role, mock_time):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_is_banned.return_value = False
        mock_role = Mock()
        mock_role.name = ROLE.MEMBER
        mock_get_role.return_value = mock_role
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_db_member = Mock()
        mock_db_member.id = 1
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_db_member)
        mock_service.disable_member = AsyncMock()
        
        with patch("ironforgedbot.effects.remove_member_role.MemberService", return_value=mock_service):
            await remove_member_role(self.mock_report_channel, self.member)
        
        self.member.remove_roles.assert_called_once()
        mock_service.disable_member.assert_called_once_with(1)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("Member disabled", call_args)

    @patch("ironforgedbot.effects.remove_member_role.time")
    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    @patch("ironforgedbot.effects.remove_member_role.db")
    async def test_handles_banned_member_differently(self, mock_db, mock_is_banned, mock_get_role, mock_time):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_is_banned.return_value = True
        mock_role = Mock()
        mock_role.name = ROLE.MEMBER
        mock_get_role.return_value = mock_role
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_db_member = Mock()
        mock_db_member.id = 1
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_db_member)
        mock_service.disable_member = AsyncMock()
        
        with patch("ironforgedbot.effects.remove_member_role.MemberService", return_value=mock_service):
            await remove_member_role(self.mock_report_channel, self.member)
        
        self.member.remove_roles.assert_called_once()
        mock_service.disable_member.assert_called_once_with(1)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("Member banned", call_args)

    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    async def test_returns_early_when_no_roles_to_remove(self, mock_is_banned, mock_get_role):
        mock_is_banned.return_value = False
        member_no_roles = create_test_member("TestUser", [], "TestUser")
        member_no_roles.id = 123456789
        member_no_roles.remove_roles = AsyncMock()
        
        await remove_member_role(self.mock_report_channel, member_no_roles)
        
        member_no_roles.remove_roles.assert_not_called()
        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    async def test_handles_forbidden_error_on_role_removal(self, mock_is_banned, mock_get_role):
        mock_is_banned.return_value = False
        mock_role = Mock()
        mock_role.name = ROLE.MEMBER
        mock_get_role.return_value = mock_role
        self.member.remove_roles.side_effect = Forbidden(Mock(), "test")
        
        await remove_member_role(self.mock_report_channel, self.member)
        
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("lacks permission", call_args)

    @patch("ironforgedbot.effects.remove_member_role.time")
    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    @patch("ironforgedbot.effects.remove_member_role.db")
    async def test_handles_member_not_found_in_database(self, mock_db, mock_is_banned, mock_get_role, mock_time):
        mock_is_banned.return_value = False
        mock_role = Mock()
        mock_role.name = ROLE.MEMBER
        mock_get_role.return_value = mock_role
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        
        with patch("ironforgedbot.effects.remove_member_role.MemberService", return_value=mock_service):
            await remove_member_role(self.mock_report_channel, self.member)
        
        self.member.remove_roles.assert_called_once()
        mock_service.disable_member.assert_not_called()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("cannot be found in the database", call_args)

    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    async def test_raises_error_when_role_not_found(self, mock_is_banned, mock_get_role):
        mock_is_banned.return_value = False
        mock_get_role.return_value = None
        
        with self.assertRaises(ValueError) as context:
            await remove_member_role(self.mock_report_channel, self.member)
        
        self.assertIn("Unable to get role", str(context.exception))

    @patch("ironforgedbot.effects.remove_member_role.time")
    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    @patch("ironforgedbot.effects.remove_member_role.text_ul")
    @patch("ironforgedbot.effects.remove_member_role.db")
    async def test_removes_multiple_roles(self, mock_db, mock_text_ul, mock_is_banned, mock_get_role, mock_time):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_is_banned.return_value = False
        mock_text_ul.return_value = "• Member\n• Iron"
        member_multi_roles = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON], "TestUser")
        member_multi_roles.id = 123456789
        member_multi_roles.mention = "<@123456789>"
        member_multi_roles.remove_roles = AsyncMock()
        mock_role1 = Mock()
        mock_role1.name = ROLE.MEMBER
        mock_role2 = Mock()
        mock_role2.name = RANK.IRON
        mock_get_role.side_effect = lambda guild, role: {
            ROLE.MEMBER: mock_role1,
            RANK.IRON: mock_role2
        }.get(role)
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_db_member = Mock()
        mock_db_member.id = 1
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_db_member)
        mock_service.disable_member = AsyncMock()
        
        with patch("ironforgedbot.effects.remove_member_role.MemberService", return_value=mock_service):
            await remove_member_role(self.mock_report_channel, member_multi_roles)
        
        member_multi_roles.remove_roles.assert_called_once()
        call_args = member_multi_roles.remove_roles.call_args[0]
        self.assertEqual(len(call_args), 2)
        mock_service.disable_member.assert_called_once_with(1)

    @patch("ironforgedbot.effects.remove_member_role.time")
    @patch("ironforgedbot.effects.remove_member_role.get_discord_role")
    @patch("ironforgedbot.effects.remove_member_role.is_member_banned")
    @patch("ironforgedbot.effects.remove_member_role.db")
    async def test_skips_banned_role_during_removal(self, mock_db, mock_is_banned, mock_get_role, mock_time):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_is_banned.return_value = False
        member_with_banned = create_test_member("TestUser", [ROLE.MEMBER, ROLE.BANNED], "TestUser")
        member_with_banned.id = 123456789
        member_with_banned.mention = "<@123456789>"
        member_with_banned.remove_roles = AsyncMock()
        mock_member_role = Mock()
        mock_member_role.name = ROLE.MEMBER
        mock_banned_role = Mock()
        mock_banned_role.name = ROLE.BANNED
        mock_get_role.side_effect = lambda guild, role: {
            ROLE.MEMBER: mock_member_role,
            ROLE.BANNED: mock_banned_role
        }.get(role)
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_db_member = Mock()
        mock_db_member.id = 1
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_db_member)
        mock_service.disable_member = AsyncMock()
        
        with patch("ironforgedbot.effects.remove_member_role.MemberService", return_value=mock_service):
            await remove_member_role(self.mock_report_channel, member_with_banned)
        
        member_with_banned.remove_roles.assert_called_once()
        call_args = member_with_banned.remove_roles.call_args[0]
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0], mock_member_role)