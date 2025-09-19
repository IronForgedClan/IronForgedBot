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
    """Test cases for MemberService class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.rollback = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.execute = AsyncMock()
        
        self.member_service = MemberService(self.mock_db)
        
        # Fixed datetime for consistent testing
        self.fixed_datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Sample member data
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
        """Test MemberService initialization"""
        self.assertEqual(self.member_service.db, self.mock_db)

    async def test_close(self):
        """Test close method calls db.close"""
        await self.member_service.close()
        self.mock_db.close.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    @patch("ironforgedbot.services.member_service.normalize_discord_string")
    @patch("ironforgedbot.services.member_service.uuid")
    async def test_create_member_success(self, mock_uuid, mock_normalize, mock_datetime):
        """Test create_member successfully creates a member with changelog"""
        mock_datetime.now.return_value = self.fixed_datetime
        mock_normalize.return_value = "normalized_nickname"
        mock_uuid.uuid4.return_value.return_value = "new-member-id"
        
        result = await self.member_service.create_member(12345, "TestNickname", RANK.IRON, "admin-id")
        
        self.assertEqual(self.mock_db.add.call_count, 2)
        
        # Check member creation
        created_member = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(created_member, Member)
        self.assertEqual(created_member.discord_id, 12345)
        self.assertEqual(created_member.nickname, "normalized_nickname")
        self.assertEqual(created_member.rank, RANK.IRON)
        self.assertTrue(created_member.active)
        self.assertEqual(created_member.ingots, 0)
        
        # Check changelog creation
        created_changelog = self.mock_db.add.call_args_list[1][0][0]
        self.assertIsInstance(created_changelog, Changelog)
        self.assertEqual(created_changelog.change_type, ChangeType.ADD_MEMBER)
        self.assertEqual(created_changelog.admin_id, "admin-id")
        self.assertEqual(created_changelog.comment, "Added member")
        
        self.mock_db.flush.assert_called_once()
        self.mock_db.commit.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_discord_id_integrity_error(self, mock_datetime):
        """Test create_member raises UniqueDiscordIdVolation on discord_id constraint"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.flush.side_effect = IntegrityError("discord_id", None, Exception())
        
        with self.assertRaises(UniqueDiscordIdVolation):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_nickname_integrity_error(self, mock_datetime):
        """Test create_member raises UniqueNicknameViolation on nickname constraint"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.flush.side_effect = IntegrityError("nickname", None, Exception())
        
        with self.assertRaises(UniqueNicknameViolation):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_unknown_integrity_error(self, mock_datetime):
        """Test create_member re-raises unknown IntegrityError"""
        mock_datetime.now.return_value = self.fixed_datetime
        error = IntegrityError("unknown", None, Exception())
        self.mock_db.flush.side_effect = error
        
        with self.assertRaises(IntegrityError):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_generic_exception(self, mock_datetime):
        """Test create_member handles generic exceptions with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.flush.side_effect = RuntimeError("Database error")
        
        with self.assertRaises(RuntimeError):
            await self.member_service.create_member(12345, "TestNickname")
        
        self.mock_db.rollback.assert_called_once()

    async def test_get_all_active_members(self):
        """Test get_all_active_members returns only active members"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [self.sample_member]
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_all_active_members()
        
        self.assertEqual(result, [self.sample_member])
        self.mock_db.execute.assert_awaited_once()

    async def test_get_member_by_id_found(self):
        """Test get_member_by_id returns member when found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_member
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_id("test-member-id")
        
        self.assertEqual(result, self.sample_member)
        self.mock_db.execute.assert_awaited_once()

    async def test_get_member_by_id_not_found(self):
        """Test get_member_by_id returns None when not found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_id("nonexistent-id")
        
        self.assertIsNone(result)

    async def test_get_member_by_discord_id_found(self):
        """Test get_member_by_discord_id returns member when found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_member
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_discord_id(12345)
        
        self.assertEqual(result, self.sample_member)

    async def test_get_member_by_discord_id_not_found(self):
        """Test get_member_by_discord_id returns None when not found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_discord_id(99999)
        
        self.assertIsNone(result)

    async def test_get_member_by_nickname_found(self):
        """Test get_member_by_nickname returns member when found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_member
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_nickname("TestUser")
        
        self.assertEqual(result, self.sample_member)

    async def test_get_member_by_nickname_not_found(self):
        """Test get_member_by_nickname returns None when not found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.member_service.get_member_by_nickname("NonExistent")
        
        self.assertIsNone(result)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_success_basic(self, mock_datetime):
        """Test reactivate_member basic functionality"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "NewNickname")
        
        self.assertIsInstance(result, MemberServiceReactivateResponse)
        self.assertTrue(result.status)
        self.assertEqual(result.previous_nick, "InactiveUser")
        self.assertTrue(result.new_member.active)
        self.assertEqual(result.new_member.nickname, "NewNickname")
        self.assertEqual(result.new_member.joined_date, self.fixed_datetime)
        
        # Should have at least 3 changelog entries: activity, join_date, nickname
        self.assertGreaterEqual(self.mock_db.add.call_count, 3)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_with_ingot_reset(self, mock_datetime):
        """Test reactivate_member resets ingots when member left more than 1 day ago"""
        mock_datetime.now.return_value = self.fixed_datetime
        # Set last_changed_date to more than 1 day ago
        old_member = self.inactive_member
        old_member.last_changed_date = self.fixed_datetime - timedelta(days=2)
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=old_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "InactiveUser")
        
        self.assertTrue(result.ingots_reset)
        self.assertEqual(result.previous_ingot_qty, 2000)
        self.assertEqual(result.new_member.ingots, 0)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_no_ingot_reset(self, mock_datetime):
        """Test reactivate_member doesn't reset ingots when member left less than 1 day ago"""
        mock_datetime.now.return_value = self.fixed_datetime
        # Set last_changed_date to less than 1 day ago
        old_member = self.inactive_member
        old_member.last_changed_date = self.fixed_datetime - timedelta(hours=12)
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=old_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "InactiveUser")
        
        self.assertFalse(result.ingots_reset)
        self.assertEqual(result.new_member.ingots, 2000)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_with_rank_change(self, mock_datetime):
        """Test reactivate_member updates rank when different rank provided"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            result = await self.member_service.reactivate_member("inactive-member-id", "InactiveUser", RANK.ADAMANT)
        
        self.assertEqual(result.previous_rank, RANK.MITHRIL)
        self.assertEqual(result.new_member.rank, RANK.ADAMANT)

    async def test_reactivate_member_not_found(self):
        """Test reactivate_member raises exception when member not found"""
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.reactivate_member("nonexistent-id", "nickname")

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_nickname_conflict(self, mock_datetime):
        """Test reactivate_member handles nickname conflict with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = IntegrityError("nickname", None, Exception())
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            with self.assertRaises(UniqueNicknameViolation):
                await self.member_service.reactivate_member("inactive-member-id", "ConflictNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_generic_exception(self, mock_datetime):
        """Test reactivate_member handles generic exceptions with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.inactive_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.reactivate_member("inactive-member-id", "nickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_disable_member_success(self, mock_datetime):
        """Test disable_member successfully deactivates member"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            result = await self.member_service.disable_member("test-member-id")
        
        self.assertFalse(result.active)
        self.assertEqual(result.last_changed_date, self.fixed_datetime)
        
        # Check changelog creation
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.change_type, ChangeType.ACTIVITY_CHANGE)
        self.assertEqual(changelog_call.previous_value, True)
        self.assertEqual(changelog_call.new_value, False)
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    async def test_disable_member_not_found(self):
        """Test disable_member raises exception when member not found"""
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.disable_member("nonexistent-id")

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_disable_member_exception_rollback(self, mock_datetime):
        """Test disable_member handles exceptions with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.disable_member("test-member-id")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_nickname_success(self, mock_datetime):
        """Test change_nickname successfully updates member nickname"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            result = await self.member_service.change_nickname("test-member-id", "NewNickname")
        
        self.assertEqual(result.nickname, "NewNickname")
        self.assertEqual(result.last_changed_date, self.fixed_datetime)
        
        # Check changelog creation
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.change_type, ChangeType.NAME_CHANGE)
        self.assertEqual(changelog_call.previous_value, "TestUser")
        self.assertEqual(changelog_call.new_value, "NewNickname")
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    async def test_change_nickname_not_found(self):
        """Test change_nickname raises exception when member not found"""
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.change_nickname("nonexistent-id", "NewNickname")

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_nickname_integrity_error(self, mock_datetime):
        """Test change_nickname handles nickname conflict with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = IntegrityError("nickname", None, Exception())
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(UniqueNicknameViolation):
                await self.member_service.change_nickname("test-member-id", "ConflictNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_nickname_generic_exception(self, mock_datetime):
        """Test change_nickname handles generic exceptions with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.change_nickname("test-member-id", "NewNickname")
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_rank_success(self, mock_datetime):
        """Test change_rank successfully updates member rank"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            result = await self.member_service.change_rank("test-member-id", RANK.ADAMANT)
        
        self.assertEqual(result.rank, RANK.ADAMANT)
        self.assertEqual(result.last_changed_date, self.fixed_datetime)
        
        # Check changelog creation
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.change_type, ChangeType.RANK_CHANGE)
        self.assertEqual(changelog_call.previous_value, RANK.IRON)
        self.assertEqual(changelog_call.new_value, RANK.ADAMANT)
        
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    async def test_change_rank_not_found(self):
        """Test change_rank raises exception when member not found"""
        with patch.object(self.member_service, 'get_member_by_id', return_value=None):
            with self.assertRaises(MemberNotFoundException):
                await self.member_service.change_rank("nonexistent-id", RANK.ADAMANT)

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_change_rank_generic_exception(self, mock_datetime):
        """Test change_rank handles generic exceptions with rollback"""
        mock_datetime.now.return_value = self.fixed_datetime
        self.mock_db.commit.side_effect = RuntimeError("Database error")
        
        with patch.object(self.member_service, 'get_member_by_id', return_value=self.sample_member):
            with self.assertRaises(RuntimeError):
                await self.member_service.change_rank("test-member-id", RANK.ADAMANT)
        
        self.mock_db.rollback.assert_called_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_create_member_default_rank(self, mock_datetime):
        """Test create_member uses default IRON rank when none provided"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        await self.member_service.create_member(12345, "TestNickname")
        
        created_member = self.mock_db.add.call_args_list[0][0][0]
        self.assertEqual(created_member.rank, RANK.IRON)

    async def test_reactivate_member_preserves_same_nickname(self):
        """Test reactivate_member doesn't create nickname changelog when nickname unchanged"""
        with patch("ironforgedbot.services.member_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = self.fixed_datetime
            
            # Set up member with recent last_changed_date to avoid ingot reset
            test_member = self.inactive_member
            test_member.last_changed_date = self.fixed_datetime - timedelta(hours=12)
            
            with patch.object(self.member_service, 'get_member_by_id', return_value=test_member):
                await self.member_service.reactivate_member("inactive-member-id", "InactiveUser", RANK.MITHRIL)
        
        # Should only have 2 changelog entries: activity and join_date (no nickname, rank, or ingot changes)
        self.assertEqual(self.mock_db.add.call_count, 2)

    async def test_reactivate_member_preserves_same_rank(self):
        """Test reactivate_member doesn't create rank changelog when rank unchanged"""
        with patch("ironforgedbot.services.member_service.datetime") as mock_datetime:
            mock_datetime.now.return_value = self.fixed_datetime
            
            # Set up member with recent last_changed_date to avoid ingot reset and different nickname
            test_member = self.inactive_member
            test_member.last_changed_date = self.fixed_datetime - timedelta(hours=12)
            
            with patch.object(self.member_service, 'get_member_by_id', return_value=test_member):
                await self.member_service.reactivate_member("inactive-member-id", "NewNickname", RANK.MITHRIL)
        
        # Should have 3 changelog entries: activity, join_date, and nickname (no rank or ingot changes)
        self.assertEqual(self.mock_db.add.call_count, 3)