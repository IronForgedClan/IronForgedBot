import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from ironforgedbot.common.activity_check import (
    build_daily_gains,
    calculate_days_of_buffer,
)


def make_snapshot(date: datetime, value: int):
    return SimpleNamespace(date=date, value=value, rank=1)


def day(offset: int) -> datetime:
    """Return a UTC datetime offset days from a fixed reference point."""
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(days=offset)


class TestCalculateDaysOfBuffer(unittest.TestCase):
    def test_returns_none_with_fewer_than_two_snapshots(self):
        self.assertIsNone(calculate_days_of_buffer([], 10000))
        self.assertIsNone(
            calculate_days_of_buffer([make_snapshot(day(0), 1000)], 10000)
        )

    def test_member_already_below_threshold_returns_zero(self):
        snapshots = [
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(29), 1_020_000),
        ]
        # xp_gained = 20_000, threshold = 50_000 → already in danger
        result = calculate_days_of_buffer(snapshots, 50_000)
        self.assertEqual(result, 0)

    def test_member_well_above_threshold_returns_many_days(self):
        # Member gains 10k XP on day 0, nothing after -> total 10k in window
        # Threshold 5k -> safe, dropping that 10k on day 30 leaves 0 -> buffer = 29 days
        snapshots = [
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(1), 1_010_000),
            make_snapshot(day(29), 1_010_000),
        ]
        result = calculate_days_of_buffer(snapshots, 5_000)
        # The 10k is gained on day 1; it falls off after 29 more simulated days
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_member_exactly_at_threshold_small_buffer(self):
        # 50k gained on day 1, nothing after. Threshold = 50k.
        # Day 0 drops off (gain=0) -> total still 50k -> safe for 1 day.
        # Day 1 drops off (gain=50k) -> total 0 → in danger.
        snapshots = [
            make_snapshot(day(0), 0),
            make_snapshot(day(1), 50_000),
            make_snapshot(day(29), 50_000),
        ]
        result = calculate_days_of_buffer(snapshots, 50_000)
        self.assertEqual(result, 1)

    def test_gains_spread_across_many_days(self):
        # 1k XP gained per day for 30 days -> total 29k
        # threshold 20k -> safe for a while
        base_xp = 1_000_000
        snapshots = [make_snapshot(day(i), base_xp + i * 1_000) for i in range(30)]
        result = calculate_days_of_buffer(snapshots, 20_000)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_uses_max_value_per_day_for_multiple_snapshots_same_day(self):
        # Multiple snapshots on day 0 — should use highest value (1_020_000).
        # Baseline = first snapshot = 1_000_000.
        # Day 0 gain = 1_020_000 - 1_000_000 = 20_000.
        # Day 29 gain = 0 (same value as day 0 max).
        # Total = 20_000, threshold = 5_000 -> active.
        # Simulating forward: day 0 drops off on first step, leaving 0 XP -> 0 days buffer.
        snapshots = [
            make_snapshot(day(0).replace(hour=8), 1_000_000),
            make_snapshot(day(0).replace(hour=20), 1_020_000),
            make_snapshot(day(29), 1_020_000),
        ]
        result = calculate_days_of_buffer(snapshots, 5_000)
        self.assertIsNotNone(result)
        self.assertEqual(result, 0)

    def test_handles_unsorted_snapshots(self):
        snapshots = [
            make_snapshot(day(29), 1_050_000),
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(15), 1_025_000),
        ]
        result = calculate_days_of_buffer(snapshots, 10_000)
        self.assertIsNotNone(result)

    def test_returns_at_most_30_days(self):
        # Enormous XP gain, tiny threshold -> capped at 30 simulation steps
        snapshots = [
            make_snapshot(day(0), 0),
            make_snapshot(day(1), 100_000_000),
            make_snapshot(day(29), 100_000_000),
        ]
        result = calculate_days_of_buffer(snapshots, 1)
        self.assertLessEqual(result, 30)


class TestBuildDailyGains(unittest.TestCase):
    def test_empty_snapshots_returns_empty(self):
        self.assertEqual(build_daily_gains([]), [])

    def test_single_snapshot_returns_empty(self):
        self.assertEqual(build_daily_gains([make_snapshot(day(0), 1_000_000)]), [])

    def test_two_snapshots_same_day_single_entry_intraday_gain(self):
        # Two snapshots on the same day -> one day.
        # Gain = max_xp(day 0) - first_snapshot_value = 1_010_000 - 1_000_000 = 10_000.
        snapshots = [
            make_snapshot(day(0).replace(hour=8), 1_000_000),
            make_snapshot(day(0).replace(hour=20), 1_010_000),
        ]
        result = build_daily_gains(snapshots)
        self.assertEqual(len(result), 1)
        _, gain = result[0]
        self.assertEqual(gain, 10_000)

    def test_correct_xp_diff_between_two_days(self):
        # Single snapshot on day 0: baseline == day 0 max -> day 0 gain = 0.
        # Day 1 gain = 1_025_000 - 1_000_000 = 25_000.
        snapshots = [
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(1), 1_025_000),
        ]
        result = build_daily_gains(snapshots)
        self.assertEqual(len(result), 2)
        _, gain_day0 = result[0]
        _, gain_day1 = result[1]
        self.assertEqual(gain_day0, 0)
        self.assertEqual(gain_day1, 25_000)

    def test_fills_gap_days_with_zero_gain(self):
        snapshots = [
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(5), 1_050_000),
        ]
        result = build_daily_gains(snapshots)
        # days 0, 1, 2, 3, 4, 5 -> 6 entries
        self.assertEqual(len(result), 6)
        # gap days (1–4) should have 0 gain
        for _, gain in result[1:5]:
            self.assertEqual(gain, 0)
        # day 5 gets the full diff
        _, gain_day5 = result[5]
        self.assertEqual(gain_day5, 50_000)

    def test_multiple_snapshots_same_day_uses_max(self):
        snapshots = [
            make_snapshot(day(0).replace(hour=8), 1_000_000),
            make_snapshot(day(0).replace(hour=18), 1_005_000),
            make_snapshot(day(1), 1_020_000),
        ]
        result = build_daily_gains(snapshots)
        self.assertEqual(len(result), 2)
        _, gain_day1 = result[1]
        # diff should be from 1_005_000 (max on day 0) to 1_020_000
        self.assertEqual(gain_day1, 15_000)

    def test_unsorted_input_is_sorted(self):
        snapshots = [
            make_snapshot(day(2), 1_030_000),
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(1), 1_010_000),
        ]
        result = build_daily_gains(snapshots)
        dates = [d for d, _ in result]
        self.assertEqual(dates, sorted(dates))

    def test_negative_diff_clamped_to_zero(self):
        # Absolute XP should never decrease, but guard against bad data.
        snapshots = [
            make_snapshot(day(0), 1_000_000),
            make_snapshot(day(1), 999_000),
        ]
        result = build_daily_gains(snapshots)
        _, gain_day1 = result[1]
        self.assertEqual(gain_day1, 0)

    def test_result_ordered_oldest_to_newest(self):
        base = 1_000_000
        snapshots = [make_snapshot(day(i), base + i * 1_000) for i in range(5)]
        result = build_daily_gains(snapshots)
        dates = [d for d, _ in result]
        self.assertEqual(dates, sorted(dates))

    def test_first_day_gain_uses_first_snapshot_as_baseline(self):
        # First snapshot is the baseline; XP gained within the first day is captured.
        # baseline = 1_000_000; day 0 max = 1_015_000 -> day 0 gain = 15_000.
        # day 1 gain = 1_040_000 - 1_015_000 = 25_000.
        snapshots = [
            make_snapshot(day(0).replace(hour=6), 1_000_000),
            make_snapshot(day(0).replace(hour=22), 1_015_000),
            make_snapshot(day(1), 1_040_000),
        ]
        result = build_daily_gains(snapshots)
        self.assertEqual(len(result), 2)
        _, gain_day0 = result[0]
        _, gain_day1 = result[1]
        self.assertEqual(gain_day0, 15_000)
        self.assertEqual(gain_day1, 25_000)
