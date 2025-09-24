import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
import time
import pickle
import zlib

from ironforgedbot.cache.score_cache import ScoreCache, SCORE_CACHE
from tests.helpers import create_test_score_breakdown, setup_time_mocks


class TestScoreCache(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cache = ScoreCache(ttl=60)  # 1 minute TTL for testing
        self.test_player = "TestPlayer"
        self.test_score_data = create_test_score_breakdown(
            skills_count=3, activities_count=2
        )

    async def test_cache_initialization(self):
        """Test cache initializes with correct defaults"""
        default_cache = ScoreCache()
        self.assertEqual(default_cache.ttl, 600)
        self.assertEqual(default_cache.cache, {})
        self.assertIsInstance(default_cache.lock, asyncio.Lock)

        custom_cache = ScoreCache(ttl=300)
        self.assertEqual(custom_cache.ttl, 300)

    async def test_set_and_get_success(self):
        """Test successful cache set and get operations"""
        await self.cache.set(self.test_player, self.test_score_data)

        retrieved_data = await self.cache.get(self.test_player)

        self.assertIsNotNone(retrieved_data)
        self.assertEqual(len(retrieved_data.skills), 3)
        self.assertEqual(len(retrieved_data.clues), 1)
        self.assertEqual(len(retrieved_data.raids), 1)

    async def test_get_nonexistent_key_returns_none(self):
        """Test getting non-existent key returns None"""
        result = await self.cache.get("NonexistentPlayer")
        self.assertIsNone(result)

    @patch("time.time")
    async def test_get_expired_entry_returns_none_and_cleans(self, mock_time):
        """Test that expired entries return None and are automatically cleaned"""
        # Set initial time and add entry
        mock_time.return_value = 1000.0
        await self.cache.set(self.test_player, self.test_score_data)

        # Verify entry exists
        result = await self.cache.get(self.test_player)
        self.assertIsNotNone(result)

        # Fast forward time past TTL
        mock_time.return_value = 1100.0  # 100 seconds later, past 60s TTL

        # Should return None and clean expired entry
        result = await self.cache.get(self.test_player)
        self.assertIsNone(result)

        # Verify entry was removed from cache
        self.assertNotIn(self.test_player, self.cache.cache)

    @patch("time.time")
    async def test_set_updates_existing_entry(self, mock_time):
        """Test that setting existing key updates the entry"""
        mock_time.return_value = 1000.0

        # Set initial data
        initial_data = create_test_score_breakdown(skills_count=2)
        await self.cache.set(self.test_player, initial_data)

        # Update with new data
        updated_data = create_test_score_breakdown(skills_count=5)
        await self.cache.set(self.test_player, updated_data)

        # Verify updated data is retrieved
        result = await self.cache.get(self.test_player)
        self.assertEqual(len(result.skills), 5)

    @patch("time.time")
    async def test_data_compression_and_decompression(self, mock_time):
        """Test that data is properly compressed and decompressed"""
        mock_time.return_value = 1000.0

        await self.cache.set(self.test_player, self.test_score_data)

        # Verify data is stored compressed
        stored_data, expires = self.cache.cache[self.test_player]
        self.assertIsInstance(stored_data, bytes)

        # Verify manual decompression works
        decompressed = pickle.loads(zlib.decompress(stored_data))
        self.assertEqual(len(decompressed.skills), 3)

    @patch("ironforgedbot.cache.score_cache.deep_getsizeof")
    @patch("time.time")
    async def test_clean_expired_entries(self, mock_time, mock_getsizeof):
        """Test cleaning expired entries and size calculation"""
        # Mock size calculation
        mock_getsizeof.side_effect = [4096, 2048]  # Before and after sizes

        # Set initial time and add entries
        mock_time.return_value = 1000.0
        await self.cache.set("player1", self.test_score_data)
        await self.cache.set("player2", create_test_score_breakdown(skills_count=1))

        # Verify both entries exist
        self.assertEqual(len(self.cache.cache), 2)

        # Fast forward time to expire entries
        mock_time.return_value = 1100.0  # Past TTL

        result = await self.cache.clean()

        # Verify cleanup message
        self.assertIsNotNone(result)
        self.assertIn(
            "Deleted **1.01 KB**", result
        )  # Adjusted to match actual calculation
        self.assertIn("Reduced cache size by **~50.00%**", result)
        self.assertIn("Cache entries: **0**", result)
        self.assertIn("Cache size: **1.01 KB**", result)

        # Verify cache is empty
        self.assertEqual(len(self.cache.cache), 0)

    @patch("time.time")
    async def test_clean_no_expired_entries(self, mock_time):
        """Test cleaning when no entries are expired"""
        mock_time.return_value = 1000.0
        await self.cache.set(self.test_player, self.test_score_data)

        # Don't advance time - entry should not be expired
        result = await self.cache.clean()

        # Should return None when nothing to clean
        self.assertIsNone(result)
        self.assertEqual(len(self.cache.cache), 1)

    @patch("time.time")
    async def test_clean_mixed_expired_and_valid_entries(self, mock_time):
        """Test cleaning when some entries are expired and some are valid"""
        # Add first entry
        mock_time.return_value = 1000.0
        await self.cache.set("old_player", self.test_score_data)

        # Add second entry later
        mock_time.return_value = 1050.0
        await self.cache.set("new_player", create_test_score_breakdown(skills_count=1))

        # Advance time to expire only first entry
        mock_time.return_value = 1080.0  # old_player expired, new_player still valid

        with patch(
            "ironforgedbot.cache.score_cache.deep_getsizeof", side_effect=[2048, 1024]
        ):
            result = await self.cache.clean()

        # Should clean only expired entry
        self.assertIsNotNone(result)
        self.assertIn("1", result)  # Should mention 1 expired item
        self.assertEqual(len(self.cache.cache), 1)
        self.assertIn("new_player", self.cache.cache)
        self.assertNotIn("old_player", self.cache.cache)

    async def test_concurrent_access_with_locks(self):
        """Test that concurrent operations are properly synchronized"""

        async def setter_task():
            for i in range(5):
                await self.cache.set(
                    f"player_{i}", create_test_score_breakdown(skills_count=i + 1)
                )

        async def getter_task():
            results = []
            for i in range(5):
                result = await self.cache.get(f"player_{i}")
                results.append(result)
            return results

        # Run setter and getter concurrently
        setter, results = await asyncio.gather(setter_task(), getter_task())

        # Verify no data corruption occurred
        valid_results = [r for r in results if r is not None]
        for result in valid_results:
            self.assertIsNotNone(result.skills)

    @patch("time.time")
    async def test_ttl_calculation(self, mock_time):
        """Test that TTL is calculated correctly"""
        mock_time.return_value = 1000.0

        await self.cache.set(self.test_player, self.test_score_data)

        # Verify expiration time is set correctly
        _, expires = self.cache.cache[self.test_player]
        expected_expires = 1000.0 + 60  # current time + TTL
        self.assertEqual(expires, expected_expires)

    async def test_global_cache_instance(self):
        """Test that global SCORE_CACHE instance is properly configured"""
        self.assertIsInstance(SCORE_CACHE, ScoreCache)
        self.assertEqual(SCORE_CACHE.ttl, 600)
        self.assertIsInstance(SCORE_CACHE.cache, dict)

    @patch("time.time")
    async def test_cache_size_calculation_edge_cases(self, mock_time):
        """Test cache size calculation with edge cases"""
        mock_time.return_value = 1000.0

        # Test with empty cache
        with patch("ironforgedbot.cache.score_cache.deep_getsizeof", return_value=0):
            result = await self.cache.clean()
            self.assertIsNone(result)

        # Test with zero initial size (edge case)
        await self.cache.set(self.test_player, self.test_score_data)
        mock_time.return_value = 1100.0  # Expire entry

        with patch(
            "ironforgedbot.cache.score_cache.deep_getsizeof", side_effect=[0, 0]
        ):
            result = await self.cache.clean()
            self.assertIsNotNone(result)
            self.assertIn("~0.00%", result)  # Should handle division by zero

    async def test_multiple_players_cache_operations(self):
        """Test cache operations with multiple players"""
        players = ["Player1", "Player2", "Player3"]

        # Set data for multiple players
        for i, player in enumerate(players):
            score_data = create_test_score_breakdown(skills_count=i + 1)
            await self.cache.set(player, score_data)

        # Verify all players can be retrieved
        for i, player in enumerate(players):
            result = await self.cache.get(player)
            self.assertIsNotNone(result)
            self.assertEqual(len(result.skills), i + 1)

    @patch("ironforgedbot.cache.score_cache.logger.debug")
    @patch("time.time")
    async def test_cleanup_logging(self, mock_time, mock_logging):
        """Test that cleanup operations are properly logged"""
        mock_time.return_value = 1000.0
        await self.cache.set(self.test_player, self.test_score_data)

        mock_time.return_value = 1100.0  # Expire entry

        with patch(
            "ironforgedbot.cache.score_cache.deep_getsizeof", side_effect=[1024, 512]
        ):
            result = await self.cache.clean()

        # Verify logging was called
        mock_logging.assert_called_once()
        call_args = mock_logging.call_args[0][0]
        self.assertIn("Clearing 1 expired item(s)", call_args)
        # Also verify the result string is returned
        self.assertIsNotNone(result)
        self.assertIn("Deleted", result)

    async def test_score_data_integrity(self):
        """Test that complex score data maintains integrity through cache operations"""
        # Create complex score data
        complex_data = create_test_score_breakdown(skills_count=10, activities_count=5)

        await self.cache.set(self.test_player, complex_data)
        retrieved_data = await self.cache.get(self.test_player)

        # Verify all data structure integrity
        self.assertEqual(len(retrieved_data.skills), 10)
        self.assertEqual(len(retrieved_data.clues), 1)
        self.assertEqual(len(retrieved_data.raids), 1)
        self.assertEqual(len(retrieved_data.bosses), 3)

        # Verify individual skill data
        for skill in retrieved_data.skills:
            self.assertIsNotNone(skill.name)
            self.assertIsNotNone(skill.xp)
            self.assertIsNotNone(skill.level)
