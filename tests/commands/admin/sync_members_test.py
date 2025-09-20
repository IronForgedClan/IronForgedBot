import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)

with patch("ironforgedbot.common.helpers.normalize_discord_string", side_effect=lambda x: x):
    from ironforgedbot.commands.admin.sync_members import sync_members


class TestSyncMembers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = Mock(spec=discord.Guild)
        self.test_member1 = create_test_member("TestUser1", [ROLE.MEMBER], "testuser1")
        self.test_member1.id = 1001
        self.test_member2 = create_test_member("TestUser2", [ROLE.MEMBER], "testuser2")
        self.test_member2.id = 1002
        self.test_member3 = create_test_member("TestUser3", [ROLE.MEMBER], "testuser3")
        self.test_member3.id = 1003

        self.db_member1 = Member(id=1, discord_id=1001, nickname="testuser1", rank=RANK.IRON, ingots=100, active=True)
        self.db_member2 = Member(id=2, discord_id=1002, nickname="oldnick", rank=RANK.IRON, ingots=200, active=True)
        self.db_member3 = Member(id=3, discord_id=9999, nickname="leftuser", rank=RANK.IRON, ingots=300, active=True)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_disable_missing_members(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member1, self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [
            self.db_member1,
            self.db_member2,
            self.db_member3,
        ]

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.disable_member.assert_called_once_with(3)
        self.assertIn(["leftuser", "Disabled", "No longer a member"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_nickname_change(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member2]

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.change_nickname.assert_called_once_with(2, "testuser2")
        self.assertIn(["testuser2", "Updated", "Nickname changed "], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_nickname_change_unique_violation(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member2]
        mock_service.change_nickname.side_effect = UniqueNicknameViolation()

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        self.assertIn(["TestUser2", "Error", "Unique nickname violation"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_rank_change(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.MITHRIL

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member1]

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.change_rank.assert_called_once_with(1, RANK.MITHRIL)
        self.assertIn(["testuser1", "Updated", "Rank changed"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_god_alignment_to_god_rank(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = GOD_ALIGNMENT.SARADOMIN

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member1]

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.change_rank.assert_called_once_with(1, RANK.GOD)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_add_new_member(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_called_once_with(1003, "testuser3", RANK.IRON)
        self.assertIn(["testuser3", "Added", "New member created"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_no_nickname_error(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        member_no_nick = create_test_member("NoNick", [ROLE.MEMBER], None)
        member_no_nick.id = 1004
        member_no_nick.nick = None

        self.guild.members = [member_no_nick]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        self.assertIn(["", "Error", "No nickname"], result)
        mock_service.create_member.assert_not_called()

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_reactivate_disabled_member(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        disabled_member = Member(id=4, discord_id=1003, nickname="testuser3", rank=RANK.IRON, ingots=0, active=False)

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = disabled_member

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.reactivate_member.assert_called_once_with(4, "testuser3", RANK.IRON)
        self.assertIn(["testuser3", "Enabled", "Returning member"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_reactivate_nickname_dupe_error(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        disabled_member = Member(id=4, discord_id=1003, nickname="testuser3", rank=RANK.IRON, ingots=0, active=False)

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = disabled_member
        mock_service.reactivate_member.side_effect = UniqueNicknameViolation()

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        self.assertIn(["[D]TestUser3", "Error", "Nickname dupe"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_data_continuity_error(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        active_member = Member(id=4, discord_id=1003, nickname="testuser3", rank=RANK.IRON, ingots=0, active=True)

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = active_member

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        self.assertIn(["testuser3", "Error", "Data continuity error"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch("ironforgedbot.commands.admin.sync_members.logger")
    async def test_sync_members_uncaught_exception(
        self, mock_logger, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = Exception("Database error")

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_logger.error.assert_called_once()
        self.assertIn(["testuser3", "Error", "Uncaught exception"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_no_rank_defaults_to_iron(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = None

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_called_once_with(1003, "testuser3", RANK.IRON)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_skip_non_members(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        non_member = create_test_member("NonMember", [ROLE.PROSPECT], "nonmember")
        non_member.id = 1005

        self.guild.members = [self.test_member1, non_member]
        mock_check_role.side_effect = lambda member, role: member.id != 1005
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member1]

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_not_called()
        self.assertEqual(len([r for r in result if "nonmember" in r[0].lower()]), 0)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_nickname_and_rank_change_combined(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.MITHRIL

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member2]

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        mock_service.change_nickname.assert_called_once_with(2, "testuser2")
        mock_service.change_rank.assert_called_once_with(2, RANK.MITHRIL)
        self.assertIn(["testuser2", "Updated", "Nickname changed Rank changed"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_output_sorted_by_nickname(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        member_z = create_test_member("ZUser", [ROLE.MEMBER], "zuser")
        member_z.id = 1006
        member_a = create_test_member("AUser", [ROLE.MEMBER], "auser")
        member_a.id = 1007

        self.guild.members = [member_z, member_a]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch("ironforgedbot.commands.admin.sync_members.MemberService", return_value=mock_service):
            result = await sync_members(self.guild)

        nicknames = [r[0] for r in result]
        self.assertEqual(nicknames, sorted(nicknames))