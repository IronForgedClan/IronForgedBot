import unittest
from datetime import datetime, timedelta, timezone
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
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            None
        )

        with self.assertRaises(ReferenceError) as context:
            await self.score_history_service.track_score(99999, 15000)

        self.assertEqual(str(context.exception), "Member with id 99999 not found")
        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(
            99999
        )

    async def test_track_score_success(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        await self.score_history_service.track_score(12345, 15000)

        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(
            12345
        )

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "test-member-id")
        self.assertEqual(score_history_call.score, 15000)
        self.assertEqual(score_history_call.nickname, "TestUser")

        self.mock_db.commit.assert_called_once()

    async def test_track_score_with_inactive_member(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.inactive_member
        )

        await self.score_history_service.track_score(99999, 8500)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "inactive-member-id")
        self.assertEqual(score_history_call.score, 8500)
        self.assertEqual(score_history_call.nickname, "InactiveUser")

        self.mock_db.commit.assert_called_once()

    async def test_track_score_zero_score(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        await self.score_history_service.track_score(12345, 0)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, 0)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_negative_score(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        await self.score_history_service.track_score(12345, -500)

        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, -500)

        self.mock_db.commit.assert_called_once()

    async def test_track_score_large_score(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

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

        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            member_with_new_nickname
        )

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

        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            different_member
        )

        await self.score_history_service.track_score(54321, 12000)

        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(
            54321
        )
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.member_id, "different-member-id")
        self.assertEqual(score_history_call.nickname, "DifferentUser")
        self.assertEqual(score_history_call.score, 12000)

    async def test_track_score_database_error_propagation(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        self.mock_db.commit.side_effect = Exception("Database connection failed")

        with self.assertRaises(Exception) as context:
            await self.score_history_service.track_score(12345, 15000)

        self.assertEqual(str(context.exception), "Database connection failed")

    async def test_track_score_member_service_error_propagation(self):
        self.score_history_service.member_service.get_member_by_discord_id.side_effect = Exception(
            "Member service failed"
        )

        with self.assertRaises(Exception) as context:
            await self.score_history_service.track_score(12345, 15000)

        self.assertEqual(str(context.exception), "Member service failed")

    async def test_track_score_validates_member_before_database_operations(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            None
        )

        with self.assertRaises(ReferenceError):
            await self.score_history_service.track_score(99999, 15000)

        self.mock_db.add.assert_not_called()
        self.mock_db.commit.assert_not_called()

    async def test_track_score_creates_correct_score_history_object(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        await self.score_history_service.track_score(12345, 15000)

        score_history_call = self.mock_db.add.call_args[0][0]

        self.assertIsInstance(score_history_call, ScoreHistory)
        self.assertEqual(score_history_call.member_id, "test-member-id")
        self.assertEqual(score_history_call.nickname, "TestUser")
        self.assertEqual(score_history_call.score, 15000)

    async def test_track_score_multiple_calls_same_member(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        await self.score_history_service.track_score(12345, 10000)

        self.mock_db.reset_mock()
        self.score_history_service.member_service.reset_mock()
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        await self.score_history_service.track_score(12345, 12000)

        self.score_history_service.member_service.get_member_by_discord_id.assert_called_once_with(
            12345
        )
        self.mock_db.add.assert_called_once()
        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.score, 12000)
        self.mock_db.commit.assert_called_once()

    async def test_track_score_different_members_sequential(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )
        await self.score_history_service.track_score(12345, 15000)

        self.mock_db.reset_mock()
        self.score_history_service.member_service.reset_mock()
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.inactive_member
        )

        await self.score_history_service.track_score(99999, 8000)

        score_history_call = self.mock_db.add.call_args[0][0]
        self.assertEqual(score_history_call.member_id, "inactive-member-id")
        self.assertEqual(score_history_call.nickname, "InactiveUser")
        self.assertEqual(score_history_call.score, 8000)


class TestGetScoreProgress(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.close = AsyncMock()

        self.score_history_service = ScoreHistoryService(self.mock_db)
        self.score_history_service.member_service = AsyncMock()

        self.now = datetime.now(tz=timezone.utc)
        self.joined_date = self.now - timedelta(days=60)

        self.sample_member = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=10000,
            joined_date=self.joined_date,
            last_changed_date=self.joined_date,
        )

    def _make_snapshot(self, score: int, date: datetime) -> ScoreHistory:
        snapshot = ScoreHistory(
            member_id="test-member-id",
            nickname="TestUser",
            score=score,
            date=date,
        )
        return snapshot

    def _mock_execute(self, snapshot: ScoreHistory | None):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = snapshot
        self.mock_db.execute = AsyncMock(return_value=mock_result)

    async def test_returns_score_for_matching_snapshot(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )
        snapshot = self._make_snapshot(10000, self.now - timedelta(days=7))
        self._mock_execute(snapshot)

        result = await self.score_history_service.get_score_progress(12345, [7])

        self.assertEqual(result[7], 10000)

    async def test_returns_none_when_no_snapshot_within_tolerance(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )
        self._mock_execute(None)

        result = await self.score_history_service.get_score_progress(12345, [7])

        self.assertIsNone(result[7])

    async def test_returns_none_when_target_predates_joined_date(self):
        member_recently_joined = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=0,
            joined_date=self.now - timedelta(days=5),
            last_changed_date=self.now,
        )
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            member_recently_joined
        )
        self.mock_db.execute = AsyncMock()

        result = await self.score_history_service.get_score_progress(12345, [7])

        self.assertIsNone(result[7])
        self.mock_db.execute.assert_not_called()

    async def test_returns_partial_results_for_mixed_periods(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        snapshot_7d = self._make_snapshot(9000, self.now - timedelta(days=7))
        snapshot_none = None

        results_sequence = []
        for snapshot in [snapshot_7d, snapshot_none, snapshot_none]:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = snapshot
            results_sequence.append(mock_result)

        self.mock_db.execute = AsyncMock(side_effect=results_sequence)

        result = await self.score_history_service.get_score_progress(
            12345, [7, 14, 30]
        )

        self.assertEqual(result[7], 9000)
        self.assertIsNone(result[14])
        self.assertIsNone(result[30])

    async def test_member_not_found_raises(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            None
        )

        with self.assertRaises(ReferenceError):
            await self.score_history_service.get_score_progress(99999, [7])

    async def test_all_periods_returned_when_snapshots_exist(self):
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            self.sample_member
        )

        snapshots = [
            self._make_snapshot(9000, self.now - timedelta(days=7)),
            self._make_snapshot(8000, self.now - timedelta(days=14)),
            self._make_snapshot(7000, self.now - timedelta(days=30)),
        ]

        results_sequence = []
        for snapshot in snapshots:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = snapshot
            results_sequence.append(mock_result)

        self.mock_db.execute = AsyncMock(side_effect=results_sequence)

        result = await self.score_history_service.get_score_progress(
            12345, [7, 14, 30]
        )

        self.assertEqual(result[7], 9000)
        self.assertEqual(result[14], 8000)
        self.assertEqual(result[30], 7000)

    async def test_period_exactly_on_joined_date_is_included(self):
        member = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=0,
            joined_date=self.now - timedelta(days=7),
            last_changed_date=self.now,
        )
        self.score_history_service.member_service.get_member_by_discord_id.return_value = (
            member
        )
        snapshot = self._make_snapshot(5000, self.now - timedelta(days=7))
        self._mock_execute(snapshot)

        result = await self.score_history_service.get_score_progress(12345, [7])

        self.assertEqual(result[7], 5000)
