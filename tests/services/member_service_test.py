import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from ironforgedbot.common.ranks import RANK
from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    MemberNotFoundException,
    MemberService,
    MemberServiceReactivateResponse,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)


class TestMemberService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.rollback = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.execute = AsyncMock()
        
        self.member_service = MemberService(self.mock_db)
        
        self.fixed_datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.sample_member = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=1000,
            rank=RANK.IRON,
            joined_date=self.fixed_datetime - timedelta(days=30),
            last_changed_date=self.fixed_datetime - timedelta(hours=1),
        )
        
        self.inactive_member = Member(
            id="inactive-member-id",
            discord_id=67890,
            active=False,
            nickname="InactiveUser",
            ingots=2000,
            rank=RANK.MITHRIL,
            joined_date=self.fixed_datetime - timedelta(days=60),
            last_changed_date=self.fixed_datetime - timedelta(days=5),
        )

    def test_init(self):
        self.assertEqual(self.member_service.db, self.mock_db)

    async def test_close(self):
        await self.member_service.close()
        self.mock_db.close.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    @patch("ironforgedbot.services.member_service.normalize_discord_string")
    @patch("ironforgedbot.services.member_service.uuid")
    async def test_create_member_success(self, mock_uuid, mock_normalize, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        mock_normalize.return_value = "normalized_nickname"
        mock_uuid.uuid4.return_value.return_value = "new-member-id"
        
        result = await self.member_service.create_member(12345, "TestNickname", RANK.IRON, "admin-id")
        
        self.assertEqual(self.mock_db.add.call_count, 2)
        
        created_member = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(created_member, Member)
        self.assertEqual(created_member.discord_id, 12345)
        self.assertEqual(created_member.nickname, "normalized_nickname")
        self.assertEqual(created_member.rank, RANK.IRON)
        self.assertTrue(created_member.active)
        self.assertEqual(created_member.ingots, 0)
        
        created_changelog = self.mock_db.add.call_args_list[1][0][0]
        self.assertIsInstance(created_changelog, Changelog)
        self.assertEqual(created_changelog.change_type, ChangeType.ADD_MEMBER)
        self.assertEqual(created_changelog.admin_id, "admin-id")
        self.assertEqual(created_changelog.comment, "Added member")
        
        self.mock_db.flush.assert_called_once()
        self.mock_db.commit.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_discord_id_integrity_error(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.flush.side_effect = IntegrityError("discord_id", None, Exception())
        
        with self.assertRaises(UniqueDiscordIdVolation):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_nickname_integrity_error(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.flush.side_effect = IntegrityError("nickname", None, Exception())
        
        with self.assertRaises(UniqueNicknameViolation):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_unknown_integrity_error(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        error = IntegrityError("unknown", None, Exception())
        self.mock_db.flush.side_effect = error
        
        with self.assertRaises(IntegrityError):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_generic_exception(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.flush.side_effect = RuntimeError("Database error")
        
        with self.assertRaises(RuntimeError):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    async def test_get_all_active_members(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [self.sample_member]
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_all_active_members()
        
        self.assertEqual(result, [self.sample_member])
        self.mock_db.execute.assert_awaited_once()

    async def test_get_member_by_id_found(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_member
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_id("test-member-id")
        
        self.assertEqual(result, self.sample_member)
        self.mock_db.execute.assert_awaited_once()

    async def test_get_member_by_id_not_found(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_id("nonexistent-id")
        
        self.assertIsNone(result)

    async def test_get_member_by_discord_id_found(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_member
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_discord_id(12345)
        
        self.assertEqual(result, self.sample_member)

    async def test_get_member_by_discord_id_not_found(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_discord_id(99999)
        
        self.assertIsNone(result)

    async def test_get_member_by_nickname_found(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_member
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_nickname("TestUser")
        
        self.assertEqual(result, self.sample_member)

    async def test_get_member_by_nickname_not_found(self):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_nickname("NonExistent")
        
        self.assertIsNone(result)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_success_basic(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "NewNickname")
        
        self.assertIsInstance(result, MemberServiceReactivateResponse)
        self.assertTrue(result.status)
        self.assertEqual(result.previous_nick, "InactiveUser")
        self.assertTrue(result.new_member.active)
        self.assertEqual(result.new_member.nickname, "NewNickname")
        self.assertEqual(result.new_member.joined_date, self.fixed_datetime)
        
        self.assertGreaterEqual(self.mock_db.add.call_count, 3)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_with_ingot_reset(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        old_member = self.inactive_member
        old_member.last_changed_date = self.fixed_datetime - timedelta(days=2)
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=old_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "InactiveUser")
        
        self.assertTrue(result.ingots_reset)
        self.assertEqual(result.previous_ingot_qty, 2000)
        self.assertEqual(result.new_member.ingots, 0)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_no_ingot_reset(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        old_member = self.inactive_member
        old_member.last_changed_date = self.fixed_datetime - timedelta(hours=12)
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=old_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "InactiveUser")
        
        self.assertFalse(result.ingots_reset)
        self.assertEqual(result.new_member.ingots, 2000)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_with_rank_change(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "InactiveUser", RANK.ADAMANT)
        
        self.assertEqual(result.previous_rank, RANK.MITHRIL)
        self.assertEqual(result.new_member.rank, RANK.ADAMANT)

    async def test_reactivate_member_not_found(self):
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.reactivate_member("nonexistent-id", "nickname")

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_nickname_conflict(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = IntegrityError("nickname", None, Exception())
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            with self.assertRaises(UniqueNicknameViolation):
                await self.member_service.reactivate_member("inactive-member-id", "ConflictNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_generic_exception(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.reactivate_member("inactive-member-id", "nickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_disable_member_success(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            result = await self.member_service.disable_member("test-member-id")
        
        self.assertFalse(result.active)
        self.assertEqual(result.last_changed_date, self.fixed_datetime)
        
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.change_type, ChangeType.ACTIVITY_CHANGE)
        self.assertEqual(changelog_call.previous_value, True)
        self.assertEqual(changelog_call.new_value, False)
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    async def test_disable_member_not_found(self):
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.disable_member("nonexistent-id")

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_disable_member_exception_rollback(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.disable_member("test-member-id")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_nickname_success(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            result = await self.member_service.change_nickname("test-member-id", "NewNickname")
        
        self.assertEqual(result.nickname, "NewNickname")
        self.assertEqual(result.last_changed_date, self.fixed_datetime)
        
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.change_type, ChangeType.NAME_CHANGE)
        self.assertEqual(changelog_call.previous_value, "TestUser")
        self.assertEqual(changelog_call.new_value, "NewNickname")
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    async def test_change_nickname_not_found(self):
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.change_nickname("nonexistent-id", "NewNickname")

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_nickname_integrity_error(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = IntegrityError("nickname", None, Exception())
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(UniqueNicknameViolation):
                await self.member_service.change_nickname("test-member-id", "ConflictNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_nickname_generic_exception(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.change_nickname("test-member-id", "NewNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_rank_success(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            result = await self.member_service.change_rank("test-member-id", RANK.ADAMANT)
        
        self.assertEqual(result.rank, RANK.ADAMANT)
        self.assertEqual(result.last_changed_date, self.fixed_datetime)
        
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.change_type, ChangeType.RANK_CHANGE)
        self.assertEqual(changelog_call.previous_value, RANK.IRON)
        self.assertEqual(changelog_call.new_value, RANK.ADAMANT)
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    async def test_change_rank_not_found(self):
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.change_rank("nonexistent-id", RANK.ADAMANT)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_rank_generic_exception(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.change_rank("test-member-id", RANK.ADAMANT)
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_default_rank(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        await self.member_service.create_member(12345, "TestNickname")
        
        created_member = self.mock_db.add.call_args_list[0][0][0]
        self.assertEqual(created_member.rank, RANK.IRON)

    async def test_reactivate_member_preserves_same_nickname(self):
        with patch("ironforgedbot.services.member_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = self.fixed_datetime
            
            test_member = self.inactive_member
            test_member.last_changed_date = self.fixed_datetime - timedelta(hours=12)
            
            with patch.object(self.member_service, 'get_member_by_id', return_value=test_member):
                await self.member_service.reactivate_member("inactive-member-id", "InactiveUser", RANK.MITHRIL)
        
        self.assertEqual(self.mock_db.add.call_count, 2)

    async def test_reactivate_member_preserves_same_rank(self):
        with patch("ironforgedbot.services.member_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = self.fixed_datetime
            
            test_member = self.inactive_member
            test_member.last_changed_date = self.fixed_datetime - timedelta(hours=12)
            
            with patch.object(self.member_service, 'get_member_by_id', return_value=test_member):
                await self.member_service.reactivate_member("inactive-member-id", "NewNickname", RANK.MITHRIL)
        
        self.assertEqual(self.mock_db.add.call_count, 3)