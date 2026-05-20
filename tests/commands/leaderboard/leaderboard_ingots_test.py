import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import VALID_CONFIG

from ironforgedbot.commands.leaderboard.leaderboard_ingots import (
    INGOTS_LEADERBOARD,
    fetch_ingots,
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
class TestFetchIngots(unittest.IsolatedAsyncioTestCase):
    async def test_returns_leaderboard_entries_for_each_member(self):
        mock_session = AsyncMock()
        mock_member_service = AsyncMock()

        member_a = AsyncMock()
        member_a.discord_id = 1
        member_a.nickname = "Alice"
        member_a.ingots = 5000
        member_a.is_prospect = False

        member_b = AsyncMock()
        member_b.discord_id = 2
        member_b.nickname = "Bob"
        member_b.ingots = 2500
        member_b.is_prospect = False

        mock_member_service.get_all_active_members.return_value = [member_a, member_b]

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_ingots.create_member_service",
            return_value=mock_member_service,
        ):
            results = await fetch_ingots(mock_session)

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
            "ironforgedbot.commands.leaderboard.leaderboard_ingots.create_member_service",
            return_value=mock_member_service,
        ):
            results = await fetch_ingots(mock_session)

        self.assertEqual(results, [])

    async def test_excludes_prospects(self):
        mock_session = AsyncMock()
        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = []

        with patch(
            "ironforgedbot.commands.leaderboard.leaderboard_ingots.create_member_service",
            return_value=mock_member_service,
        ):
            await fetch_ingots(mock_session)

        mock_member_service.get_all_active_members.assert_called_once_with(
            include_prospects=False
        )


@patch.dict("os.environ", VALID_CONFIG)
class TestIngotsLeaderboard(unittest.TestCase):
    def test_is_leaderboard_config(self):
        self.assertIsInstance(INGOTS_LEADERBOARD, LeaderboardConfig)

    def test_has_required_fields(self):
        self.assertTrue(INGOTS_LEADERBOARD.title)
        self.assertTrue(INGOTS_LEADERBOARD.description)
        self.assertTrue(INGOTS_LEADERBOARD.column_header)
        self.assertTrue(callable(INGOTS_LEADERBOARD.sort_key))
        self.assertTrue(callable(INGOTS_LEADERBOARD.value_formatter))
        self.assertTrue(callable(INGOTS_LEADERBOARD.fetcher))

    def test_sort_key_returns_value(self):
        entry = _make_entry(value=5000)
        self.assertEqual(INGOTS_LEADERBOARD.sort_key(entry), 5000)

    def test_value_formatter_formats_with_commas(self):
        entry = _make_entry(value=1234567)
        self.assertEqual(INGOTS_LEADERBOARD.value_formatter(entry), "1,234,567")


if __name__ == "__main__":
    unittest.main()
