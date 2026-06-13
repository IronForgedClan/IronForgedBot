import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import VALID_CONFIG

from ironforgedbot.commands.leaderboard.leaderboard_staff import (
    STAFF_LEADERBOARD,
    fetch_staff,
)
from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    StaffLeaderboardEntry,
)
from ironforgedbot.common.ranks import RANK


def _make_entry(
    nickname: str = "StaffPlayer",
    value: int = 5000,
    discord_id: int = 12345,
    rank: RANK = RANK.MYTH,
) -> StaffLeaderboardEntry:
    return StaffLeaderboardEntry(
        discord_id=discord_id, nickname=nickname, value=value, rank=rank
    )


@patch.dict("os.environ", VALID_CONFIG)
class TestFetchStaff(unittest.IsolatedAsyncioTestCase):
    async def test_returns_staff_leaderboard_entries_for_each_row(self):
        mock_session = AsyncMock()
        mock_score_service = AsyncMock()
        mock_score_service.get_staff_score_snapshot.return_value = [
            (10, "StaffA", 15000, RANK.MYTH),
            (20, "StaffB", 9500, RANK.LEGEND),
        ]

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_staff.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await fetch_staff(mock_session)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0],
            StaffLeaderboardEntry(
                discord_id=10, nickname="StaffA", value=15000, rank=RANK.MYTH
            ),
        )
        self.assertEqual(
            results[1],
            StaffLeaderboardEntry(
                discord_id=20, nickname="StaffB", value=9500, rank=RANK.LEGEND
            ),
        )

    async def test_returns_empty_list_when_no_staff(self):
        mock_session = AsyncMock()
        mock_score_service = AsyncMock()
        mock_score_service.get_staff_score_snapshot.return_value = []

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_staff.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await fetch_staff(mock_session)

        self.assertEqual(results, [])

    async def test_entry_rank_is_preserved(self):
        mock_session = AsyncMock()
        mock_score_service = AsyncMock()
        mock_score_service.get_staff_score_snapshot.return_value = [
            (10, "StaffA", 20000, RANK.GOD),
        ]

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_staff.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await fetch_staff(mock_session)

        self.assertEqual(results[0].rank, RANK.GOD)


@patch.dict("os.environ", VALID_CONFIG)
class TestStaffLeaderboard(unittest.TestCase):
    def test_is_leaderboard_config(self):
        self.assertIsInstance(STAFF_LEADERBOARD, LeaderboardConfig)

    def test_has_required_fields(self):
        self.assertTrue(STAFF_LEADERBOARD.title)
        self.assertTrue(STAFF_LEADERBOARD.description)
        self.assertTrue(STAFF_LEADERBOARD.column_header)
        self.assertTrue(callable(STAFF_LEADERBOARD.sort_key))
        self.assertTrue(callable(STAFF_LEADERBOARD.value_formatter))
        self.assertTrue(callable(STAFF_LEADERBOARD.fetcher))

    def test_sort_key_returns_value(self):
        entry = _make_entry(value=15000)
        self.assertEqual(STAFF_LEADERBOARD.sort_key(entry), 15000)

    def test_value_formatter_formats_with_commas(self):
        entry = _make_entry(value=1234567)
        self.assertEqual(STAFF_LEADERBOARD.value_formatter(entry), "1,234,567")

    def test_column_header_is_score(self):
        self.assertEqual(STAFF_LEADERBOARD.column_header, "Score")


if __name__ == "__main__":
    unittest.main()
