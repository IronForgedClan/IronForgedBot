import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.member import Member
from ironforgedbot.models.score_history import ScoreHistory
from ironforgedbot.services.score_history_service import ScoreHistoryService


class TestScoreHistoryService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.close = AsyncMock()

        self.score_history_service = ScoreHistoryService(self.mock_db)
        self.score_history_service.member_service = AsyncMock()

        self.fixed_datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

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

        self.sample_score_history = ScoreHistory(
            id=1,
            member_id="test-member-id",
            nickname="TestUser",
            score=15000,
            date=self.fixed_datetime,
        )

    def test_init(self):
        service = ScoreHistoryService(self.mock_db)
        self.assertEqual(service.db, self.mock_db)
        self.assertIsNotNone(service.member_service)

    async def test_close(self):
        await self.score_history_service.close()

        self.score_history_service.member_service.close.assert_called_once()
        self.mock_db.close.assert_called_once()


    async def test_track_score_member_not_found(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = None

        with self.assertRaises(ReferenceError) as context:
            await self.score_history_service.track_score(99999, 15000)

        self.assertEqual(str(context.exception), "Member with id 99999 not found")
        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(99999)

    async def test_track_score_success(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 15000)

        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(12345)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "test-member-id")
        self.assertEqual(score_history_call.score, 15000)
        self.assertEqual(score_history_call.nickname, "TestUser")

        self.mock_db.commit.assert_called_once()

    async def test_track_score_with_inactive_member(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.inactive_member

        await self.score_history_service.track_score(99999, 8500)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "inactive-member-id")
        self.assertEqual(score_history_call.score, 8500)
        self.assertEqual(score_history_call.nickname, "InactiveUser")

        self.mock_db.commit.assert_called_once()

    async def test_track_score_zero_score(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 0)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, 0)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_negative_score(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, -500)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, -500)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_large_score(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        large_score = 1_000_000_000
        await self.score_history_service.track_score(12345, large_score)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, large_score)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_uses_current_member_nickname(self):
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

        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.nickname, "NewNickname")

    async def test_track_score_different_discord_ids(self):
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

        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(54321)
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.member_id, "different-member-id")
        self.assertEqual(score_history_call.nickname, "DifferentUser")
        self.assertEqual(score_history_call.score, 12000)


    async def test_track_score_database_error_propagation(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        self.mock_db.commit.side_effect = Exception("Database connection failed")

        with self.assertRaises(Exception) as context:
            await self.score_history_service.track_score(12345, 15000)

        self.assertEqual(str(context.exception), "Database connection failed")

    async def test_track_score_member_service_error_propagation(self):
        self.score_history_service.member_service.get_member_by_discord_id.side_effect = Exception("Member service failed")

        with self.assertRaises(Exception) as context:
            await self.score_history_service.track_score(12345, 15000)

        self.assertEqual(str(context.exception), "Member service failed")

    async def test_track_score_validates_member_before_database_operations(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = None

        with self.assertRaises(ReferenceError):
            await self.score_history_service.track_score(99999, 15000)

        self.mock_db.add.assert_not_called()
        self.mock_db.commit.assert_not_called()


    async def test_track_score_creates_correct_score_history_object(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 15000)

        score_history_call = self.mock_db.add.call_args[0][0]
        
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "test-member-id")
        self.assertEqual(score_history_call.nickname, "TestUser")
        self.assertEqual(score_history_call.score, 15000)

    async def test_track_score_multiple_calls_same_member(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 10000)
        
        self.mock_db.reset_mock()
        self.score_history_service.member_service.reset_mock()
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member

        await self.score_history_service.track_score(12345, 12000)

        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(12345)
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, 12000)
        self.mock_db.commit.assert_called_once()

    async def test_track_score_different_members_sequential(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        await self.score_history_service.track_score(12345, 15000)

        self.mock_db.reset_mock()
        self.score_history_service.member_service.reset_mock()
        self.score_history_service.member_service.get_member_by_discord_id.return_value = self.inactive_member
        
        await self.score_history_service.track_score(99999, 8000)

        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.member_id, "inactive-member-id")
        self.assertEqual(score_history_call.nickname, "InactiveUser")
        self.assertEqual(score_history_call.score, 8000)