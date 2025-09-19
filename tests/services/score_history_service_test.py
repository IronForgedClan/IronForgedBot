import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.member import Member
from ironforgedbot.models.score_history import ScoreHistory
from ironforgedbot.services.score_history_service import ScoreHistoryService


class TestScoreHistoryService(unittest.IsolatedAsyncioTestCase):
    """Test cases for ScoreHistoryService class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.close = AsyncMock()

        self.score_history_service = ScoreHistoryService(self.mock_db)
        self.score_history_service.member_service = AsyncMock()

        # Fixed datetime for consistent testing
        self.fixed_datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Sample member data
        self.sample_member = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=10000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )

        self.inactive_member = Member(
            id="inactive-member-id",
            discord_id=99999,
            active=False,
            nickname="InactiveUser",
            ingots=5000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )

        # Sample score history
        self.sample_score_history = ScoreHistory(
            id=1,
            member_id="test-member-id",
            nickname="TestUser",
            score=15000,
            date=self.fixed_datetime,
        )

    def test_init(self):
        """Test ScoreHistoryService initialization"""
        service = ScoreHistoryService(self.mock_db)
        self.assertEqual(service.db, self.mock_db)
        self.assertIsNotNone(service.member_service)

    async def test_close(self):
        """Test close method calls both member_service.close and db.close"""
        await self.score_history_service.close()

        self.score_history_service.member_service.close.assert_called_once()
        self.mock_db.close.assert_called_once()

    # =============================================================================
    # track_score tests
    # =============================================================================

    async def test_track_score_member_not_found(self):
        """Test track_score raises ReferenceError when member not found"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = None

        with self.assertRaises(ReferenceError) as context:
            await self.score_history_service.track_score(99999, 15000)

        self.assertEqual(str(context.exception), "Member with id 99999 not found")
        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(99999)

    async def test_track_score_success(self):
        """Test track_score successfully creates score history record"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 15000)

        # Verify member lookup
        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(12345)

        # Verify score history was added
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "test-member-id")
        self.assertEqual(score_history_call.score, 15000)
        self.assertEqual(score_history_call.nickname, "TestUser")

        # Verify commit was called
        self.mock_db.commit.assert_called_once()

    async def test_track_score_with_inactive_member(self):
        """Test track_score works with inactive members"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.inactive_member

        await self.score_history_service.track_score(99999, 8500)

        # Verify score history was added even for inactive member
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "inactive-member-id")
        self.assertEqual(score_history_call.score, 8500)
        self.assertEqual(score_history_call.nickname, "InactiveUser")

        self.mock_db.commit.assert_called_once()

    async def test_track_score_zero_score(self):
        """Test track_score handles zero score correctly"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 0)

        # Verify score history was added with zero score
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, 0)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_negative_score(self):
        """Test track_score handles negative scores correctly"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, -500)

        # Verify score history was added with negative score
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, -500)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_large_score(self):
        """Test track_score handles very large scores correctly"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        large_score = 1_000_000_000
        await self.score_history_service.track_score(12345, large_score)

        # Verify score history was added with large score
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, large_score)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_uses_current_member_nickname(self):
        """Test track_score uses the member's current nickname"""
        # Create member with different nickname
        member_with_new_nickname = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="NewNickname",
            ingots=10000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )

        self.score_history_service.member_service.get_member_by_discord_id.return_value = member_with_new_nickname

        await self.score_history_service.track_score(12345, 15000)

        # Verify score history uses current nickname
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.nickname, "NewNickname")

    async def test_track_score_different_discord_ids(self):
        """Test track_score works with different discord IDs"""
        # Test with different member
        different_member = Member(
            id="different-member-id",
            discord_id=54321,
            active=True,
            nickname="DifferentUser",
            ingots=5000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )

        self.score_history_service.member_service.get_member_by_discord_id.return_value = different_member

        await self.score_history_service.track_score(54321, 12000)

        # Verify correct member data was used
        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(54321)
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.member_id, "different-member-id")
        self.assertEqual(score_history_call.nickname, "DifferentUser")
        self.assertEqual(score_history_call.score, 12000)

    # =============================================================================
    # Error handling and edge cases
    # =============================================================================

    async def test_track_score_database_error_propagation(self):
        """Test track_score propagates database errors correctly"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock database commit to raise an exception
        self.mock_db.commit.side_effect = Exception("Database connection failed")

        with self.assertRaises(Exception) as context:
            await self.score_history_service.track_score(12345, 15000)

        self.assertEqual(str(context.exception), "Database connection failed")

    async def test_track_score_member_service_error_propagation(self):
        """Test track_score propagates member service errors correctly"""
        # Mock member service to raise an exception
        self.score_history_service.member_service.get_member_by_discord_id.side_effect = Exception("Member service failed")

        with self.assertRaises(Exception) as context:
            await self.score_history_service.track_score(12345, 15000)

        self.assertEqual(str(context.exception), "Member service failed")

    async def test_track_score_validates_member_before_database_operations(self):
        """Test track_score validates member existence before any database operations"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = None

        with self.assertRaises(ReferenceError):
            await self.score_history_service.track_score(99999, 15000)

        # Verify no database operations were attempted
        self.mock_db.add.assert_not_called()
        self.mock_db.commit.assert_not_called()

    # =============================================================================
    # Integration and consistency tests
    # =============================================================================

    async def test_track_score_creates_correct_score_history_object(self):
        """Test track_score creates ScoreHistory object with all correct fields"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 15000)

        score_history_call = self.mock_db.add.call_args[0][0]
        
        # Verify all fields are correctly set
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "test-member-id")
        self.assertEqual(score_history_call.nickname, "TestUser")
        self.assertEqual(score_history_call.score, 15000)
        # Note: date field uses default datetime.now(timezone.utc) so we can't easily test exact value

    async def test_track_score_multiple_calls_same_member(self):
        """Test track_score can be called multiple times for the same member"""
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        # First call
        await self.score_history_service.track_score(12345, 10000)
        
        # Reset mocks to isolate second call
        self.mock_db.reset_mock()
        self.score_history_service.member_service.reset_mock()
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        # Second call with different score
        await self.score_history_service.track_score(12345, 12000)

        # Verify second call worked independently
        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(12345)
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, 12000)
        self.mock_db.commit.assert_called_once()

    async def test_track_score_different_members_sequential(self):
        """Test track_score works correctly for different members in sequence"""
        # First member
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        await self.score_history_service.track_score(12345, 15000)

        # Reset and test second member
        self.mock_db.reset_mock()
        self.score_history_service.member_service.reset_mock()
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.inactive_member
        
        await self.score_history_service.track_score(99999, 8000)

        # Verify second call used correct member data
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.member_id, "inactive-member-id")
        self.assertEqual(score_history_call.nickname, "InactiveUser")
        self.assertEqual(score_history_call.score, 8000)