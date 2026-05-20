import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import VALID_CONFIG

from ironforgedbot.commands.leaderboard.leaderboard_score import (
    SCORE_LEADERBOARD,
    fetch_scores,
)
from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    LeaderboardEntry,
)


def _make_entry(
    nickname: str = "Player",
    value: int = 1000,
    discord_id: int = 12345,
) -> LeaderboardEntry:
    return LeaderboardEntry(discord_id=discord_id, nickname=nickname, value=value)


@patch.dict("os.environ", VALID_CONFIG)
class TestFetchScores(unittest.IsolatedAsyncioTestCase):
    async def test_returns_leaderboard_entries_for_each_row(self):
        mock_session = AsyncMock()
        mock_score_service = AsyncMock()
        mock_score_service.get_latest_score_snapshot.return_value = [
            (10, "PlayerA", 99000),
            (20, "PlayerB", 45000),
        ]

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_score.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await fetch_scores(mock_session)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0], LeaderboardEntry(discord_id=10, nickname="PlayerA", value=99000)
        )
        self.assertEqual(
            results[1], LeaderboardEntry(discord_id=20, nickname="PlayerB", value=45000)
        )

    async def test_returns_empty_list_when_no_rows(self):
        mock_session = AsyncMock()
        mock_score_service = AsyncMock()
        mock_score_service.get_latest_score_snapshot.return_value = []

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_score.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await fetch_scores(mock_session)

        self.assertEqual(results, [])


@patch.dict("os.environ", VALID_CONFIG)
class TestScoreLeaderboard(unittest.TestCase):
    def test_is_leaderboard_config(self):
        self.assertIsInstance(SCORE_LEADERBOARD, LeaderboardConfig)

    def test_has_required_fields(self):
        self.assertTrue(SCORE_LEADERBOARD.title)
        self.assertTrue(SCORE_LEADERBOARD.description)
        self.assertTrue(SCORE_LEADERBOARD.column_header)
        self.assertTrue(callable(SCORE_LEADERBOARD.sort_key))
        self.assertTrue(callable(SCORE_LEADERBOARD.value_formatter))
        self.assertTrue(callable(SCORE_LEADERBOARD.fetcher))

    def test_sort_key_returns_value(self):
        entry = _make_entry(value=99000)
        self.assertEqual(SCORE_LEADERBOARD.sort_key(entry), 99000)

    def test_value_formatter_formats_with_commas(self):
        entry = _make_entry(value=1234567)
        self.assertEqual(SCORE_LEADERBOARD.value_formatter(entry), "1,234,567")


if __name__ == "__main__":
    unittest.main()
