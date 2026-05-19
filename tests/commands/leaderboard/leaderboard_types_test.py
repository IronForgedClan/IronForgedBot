import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import VALID_CONFIG

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LEADERBOARD_TYPES,
    LeaderboardConfig,
    LeaderboardEntry,
    _fetch_ingots,
    _fetch_scores,
)


def _make_entry(
    nickname: str = "Player",
    value: int = 1000,
    discord_id: int = 12345,
) -> LeaderboardEntry:
    return LeaderboardEntry(discord_id=discord_id, nickname=nickname, value=value)


@patch.dict("os.environ", VALID_CONFIG)
class TestFetchIngots(unittest.IsolatedAsyncioTestCase):
    async def test_returns_leaderboard_entries_for_each_member(self):
        mock_session = AsyncMock()
        mock_member_service = AsyncMock()

        member_a = AsyncMock()
        member_a.discord_id = 1
        member_a.nickname = "Alice"
        member_a.ingots = 5000

        member_b = AsyncMock()
        member_b.discord_id = 2
        member_b.nickname = "Bob"
        member_b.ingots = 2500

        mock_member_service.get_all_active_members.return_value = [member_a, member_b]

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_types.create_member_service",
            return_value=mock_member_service,
        ):
            results = await _fetch_ingots(mock_session)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0], LeaderboardEntry(discord_id=1, nickname="Alice", value=5000)
        )
        self.assertEqual(
            results[1], LeaderboardEntry(discord_id=2, nickname="Bob", value=2500)
        )

    async def test_returns_empty_list_when_no_members(self):
        mock_session = AsyncMock()
        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = []

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_types.create_member_service",
            return_value=mock_member_service,
        ):
            results = await _fetch_ingots(mock_session)

        self.assertEqual(results, [])


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
            "ironforgedbot.commands.leaderboard.leaderboard_types.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await _fetch_scores(mock_session)

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
            "ironforgedbot.commands.leaderboard.leaderboard_types.create_score_history_service",
            return_value=mock_score_service,
        ):
            results = await _fetch_scores(mock_session)

        self.assertEqual(results, [])


@patch.dict("os.environ", VALID_CONFIG)
class TestLeaderboardConfig(unittest.TestCase):
    def test_ingots_type_registered(self):
        self.assertIn("ingots", LEADERBOARD_TYPES)

    def test_score_type_registered(self):
        self.assertIn("score", LEADERBOARD_TYPES)

    def test_ingots_config_has_required_fields(self):
        config = LEADERBOARD_TYPES["ingots"]
        self.assertIsInstance(config, LeaderboardConfig)
        self.assertTrue(config.title)
        self.assertTrue(config.description)
        self.assertTrue(config.column_header)
        self.assertTrue(callable(config.sort_key))
        self.assertTrue(callable(config.value_formatter))
        self.assertTrue(callable(config.fetcher))

    def test_score_config_has_required_fields(self):
        config = LEADERBOARD_TYPES["score"]
        self.assertIsInstance(config, LeaderboardConfig)
        self.assertTrue(config.title)
        self.assertTrue(config.description)
        self.assertTrue(config.column_header)
        self.assertTrue(callable(config.sort_key))
        self.assertTrue(callable(config.value_formatter))
        self.assertTrue(callable(config.fetcher))

    def test_ingots_sort_key_returns_value(self):
        entry = _make_entry(value=5000)
        config = LEADERBOARD_TYPES["ingots"]
        self.assertEqual(config.sort_key(entry), 5000)

    def test_ingots_value_formatter_formats_with_commas(self):
        entry = _make_entry(value=1234567)
        config = LEADERBOARD_TYPES["ingots"]
        self.assertEqual(config.value_formatter(entry), "1,234,567")

    def test_score_sort_key_returns_value(self):
        entry = _make_entry(value=99000)
        config = LEADERBOARD_TYPES["score"]
        self.assertEqual(config.sort_key(entry), 99000)

    def test_score_value_formatter_formats_with_commas(self):
        entry = _make_entry(value=1234567)
        config = LEADERBOARD_TYPES["score"]
        self.assertEqual(config.value_formatter(entry), "1,234,567")


if __name__ == "__main__":
    unittest.main()
