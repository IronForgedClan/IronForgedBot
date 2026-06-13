import unittest

from tests.helpers import VALID_CONFIG
from unittest.mock import patch

from ironforgedbot.commands.leaderboard.leaderboard_registry import LEADERBOARD_TYPES
from ironforgedbot.commands.leaderboard.leaderboard_types import LeaderboardConfig


@patch.dict("os.environ", VALID_CONFIG)
class TestLeaderboardRegistry(unittest.TestCase):
    def test_ingots_type_registered(self):
        self.assertIn("ingots", LEADERBOARD_TYPES)

    def test_score_type_registered(self):
        self.assertIn("score", LEADERBOARD_TYPES)

    def test_staff_type_registered(self):
        self.assertIn("staff", LEADERBOARD_TYPES)

    def test_all_entries_are_leaderboard_configs(self):
        for key, config in LEADERBOARD_TYPES.items():
            with self.subTest(key=key):
                self.assertIsInstance(config, LeaderboardConfig)


if __name__ == "__main__":
    unittest.main()
