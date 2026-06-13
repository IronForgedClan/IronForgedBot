import unittest
from unittest.mock import patch

import discord

from ironforgedbot.commands.leaderboard.leaderboard_embeds import (
    build_leaderboard_embeds,
    build_staff_leaderboard_embeds,
    find_caller_page,
)
from ironforgedbot.commands.leaderboard.leaderboard_registry import LEADERBOARD_TYPES
from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardEntry,
    StaffLeaderboardEntry,
)
from ironforgedbot.common.ranks import RANK
from tests.helpers import VALID_CONFIG


def _make_entry(
    nickname: str = "Player",
    value: int = 1000,
    discord_id: int = 12345,
) -> LeaderboardEntry:
    return LeaderboardEntry(discord_id=discord_id, nickname=nickname, value=value)


@patch.dict("os.environ", VALID_CONFIG)
class TestBuildLeaderboardEmbeds(unittest.TestCase):
    def setUp(self):
        self.config = LEADERBOARD_TYPES["ingots"]

    def test_empty_entries_returns_single_embed(self):
        embeds = build_leaderboard_embeds([], self.config)
        self.assertEqual(len(embeds), 1)
        self.assertIn("No members found", embeds[0].description)

    def test_empty_entries_includes_description(self):
        embeds = build_leaderboard_embeds([], self.config)
        self.assertIn(self.config.description, embeds[0].description)

    def test_single_page_returns_one_embed(self):
        entries = [
            _make_entry(nickname=f"Player{i}", value=1000 - i, discord_id=i)
            for i in range(10)
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        self.assertEqual(len(embeds), 1)

    def test_multiple_pages_correct_count(self):
        entries = [
            _make_entry(nickname=f"Player{i}", value=1000 - i, discord_id=i)
            for i in range(60)
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        self.assertEqual(len(embeds), 3)

    def test_embed_contains_member_names(self):
        entries = [
            _make_entry(nickname="TopPlayer", value=9999, discord_id=1),
            _make_entry(nickname="MidPlayer", value=5000, discord_id=2),
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        self.assertIn("TopPlayer", embeds[0].description)
        self.assertIn("MidPlayer", embeds[0].description)

    def test_rank_numbers_are_continuous_across_pages(self):
        entries = [
            _make_entry(nickname=f"Player{i}", value=1000 - i, discord_id=i)
            for i in range(30)
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        self.assertIn("1 ", embeds[0].description)
        self.assertIn("26 ", embeds[1].description)

    def test_single_page_has_no_page_indicator(self):
        entries = [
            _make_entry(nickname=f"Player{i}", value=100 - i, discord_id=i)
            for i in range(5)
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        self.assertNotIn("Page 1 of", embeds[0].description)

    def test_multiple_pages_have_page_indicator(self):
        entries = [
            _make_entry(nickname=f"Player{i}", value=1000 - i, discord_id=i)
            for i in range(30)
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        self.assertIn("page 1 of 2", embeds[0].description)
        self.assertIn("page 2 of 2", embeds[1].description)

    def test_embed_title_matches_config(self):
        entries = [_make_entry(value=500)]
        embeds = build_leaderboard_embeds(entries, self.config)
        self.assertEqual(embeds[0].title, self.config.title)

    def test_embed_uses_code_block(self):
        entries = [_make_entry(value=500)]
        embeds = build_leaderboard_embeds(entries, self.config)
        self.assertIn("```", embeds[0].description)

    def test_values_formatted_with_commas(self):
        entries = [_make_entry(nickname="Wealthy", value=1234567)]
        embeds = build_leaderboard_embeds(entries, self.config)
        self.assertIn("1,234,567", embeds[0].description)

    def test_description_appears_on_every_page(self):
        entries = [
            _make_entry(nickname=f"Player{i}", value=1000 - i, discord_id=i)
            for i in range(30)
        ]
        embeds = build_leaderboard_embeds(entries, self.config, page_size=25)
        for embed in embeds:
            self.assertIn(self.config.description, embed.description)

    def test_description_appears_above_table(self):
        entries = [_make_entry(nickname="Player", value=500)]
        embeds = build_leaderboard_embeds(entries, self.config)
        desc = embeds[0].description
        self.assertLess(desc.index(self.config.description), desc.index("```"))


@patch.dict("os.environ", VALID_CONFIG)
class TestFindCallerPage(unittest.TestCase):
    def test_returns_none_when_not_found(self):
        entries = [_make_entry(discord_id=111), _make_entry(discord_id=222)]
        self.assertIsNone(find_caller_page(entries, 999))

    def test_returns_one_for_entry_on_first_page(self):
        entries = [_make_entry(discord_id=i + 1) for i in range(10)]
        result = find_caller_page(entries, discord_id=5, page_size=25)
        self.assertEqual(result, 1)

    def test_returns_two_for_entry_on_second_page(self):
        entries = [_make_entry(discord_id=i + 1) for i in range(30)]
        result = find_caller_page(entries, discord_id=26, page_size=25)
        self.assertEqual(result, 2)

    def test_returns_one_for_first_entry(self):
        entries = [_make_entry(discord_id=42)]
        self.assertEqual(find_caller_page(entries, 42, page_size=25), 1)

    def test_boundary_last_entry_of_page_one(self):
        entries = [_make_entry(discord_id=i + 1) for i in range(25)]
        result = find_caller_page(entries, discord_id=25, page_size=25)
        self.assertEqual(result, 1)

    def test_boundary_first_entry_of_page_two(self):
        entries = [_make_entry(discord_id=i + 1) for i in range(26)]
        result = find_caller_page(entries, discord_id=26, page_size=25)
        self.assertEqual(result, 2)

    def test_empty_entry_list_returns_none(self):
        self.assertIsNone(find_caller_page([], 42))


def _make_staff_entry(
    nickname: str = "StaffPlayer",
    value: int = 5000,
    discord_id: int = 12345,
    rank: RANK = RANK.MYTH,
) -> StaffLeaderboardEntry:
    return StaffLeaderboardEntry(
        discord_id=discord_id, nickname=nickname, value=value, rank=rank
    )


@patch.dict("os.environ", VALID_CONFIG)
class TestBuildStaffLeaderboardEmbeds(unittest.TestCase):
    def setUp(self):
        self.config = LEADERBOARD_TYPES["staff"]

    def test_empty_entries_returns_single_embed(self):
        embeds = build_staff_leaderboard_embeds([], self.config)
        self.assertEqual(len(embeds), 1)
        self.assertIn("No members found", embeds[0].description)

    def test_empty_entries_includes_description(self):
        embeds = build_staff_leaderboard_embeds([], self.config)
        self.assertIn(self.config.description, embeds[0].description)

    def test_single_page_for_small_group(self):
        entries = [
            _make_staff_entry(nickname=f"Staff{i}", discord_id=i, rank=RANK.MYTH)
            for i in range(5)
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config, page_size=20)
        self.assertEqual(len(embeds), 1)

    def test_rank_subheading_appears_in_embed(self):
        entries = [_make_staff_entry(nickname="TopStaff", rank=RANK.MYTH)]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        self.assertIn("Myth", embeds[0].description)

    def test_member_name_appears_in_embed(self):
        entries = [_make_staff_entry(nickname="TopStaff", rank=RANK.MYTH)]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        self.assertIn("TopStaff", embeds[0].description)

    def test_multiple_rank_groups_appear_in_correct_order(self):
        entries = [
            _make_staff_entry(nickname="MythPlayer", rank=RANK.MYTH, value=14000),
            _make_staff_entry(nickname="LegendPlayer", rank=RANK.LEGEND, value=9000),
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        desc = embeds[0].description
        self.assertLess(desc.index("Myth"), desc.index("Legend"))

    def test_within_group_sorted_by_score_descending(self):
        entries = [
            _make_staff_entry(
                nickname="LowMythPlayer", rank=RANK.MYTH, value=13000, discord_id=1
            ),
            _make_staff_entry(
                nickname="HighMythPlayer", rank=RANK.MYTH, value=19000, discord_id=2
            ),
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        desc = embeds[0].description
        self.assertLess(desc.index("HighMythPlayer"), desc.index("LowMythPlayer"))

    def test_global_rank_numbers_are_continuous(self):
        entries = [
            _make_staff_entry(nickname="MythPlayer", rank=RANK.MYTH, value=14000),
            _make_staff_entry(nickname="LegendPlayer", rank=RANK.LEGEND, value=9000),
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        desc = embeds[0].description
        self.assertIn("1  MythPlayer", desc)
        self.assertIn("2  LegendPlayer", desc)

    def test_rank_group_not_split_across_pages(self):
        entries = [
            _make_staff_entry(
                nickname=f"MythPlayer{i}", rank=RANK.MYTH, value=20000 - i, discord_id=i
            )
            for i in range(15)
        ] + [
            _make_staff_entry(
                nickname=f"LegendPlayer{i}",
                rank=RANK.LEGEND,
                value=9000 - i,
                discord_id=100 + i,
            )
            for i in range(10)
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config, page_size=20)
        self.assertEqual(len(embeds), 2)
        self.assertIn("Myth", embeds[0].description)
        self.assertNotIn("Myth", embeds[1].description)
        self.assertIn("Legend", embeds[1].description)

    def test_multiple_pages_have_page_indicator(self):
        entries = [
            _make_staff_entry(
                nickname=f"MythPlayer{i}", rank=RANK.MYTH, value=20000 - i, discord_id=i
            )
            for i in range(15)
        ] + [
            _make_staff_entry(
                nickname=f"LegendPlayer{i}",
                rank=RANK.LEGEND,
                value=9000 - i,
                discord_id=100 + i,
            )
            for i in range(10)
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config, page_size=20)
        self.assertIn("page 1 of 2", embeds[0].description)
        self.assertIn("page 2 of 2", embeds[1].description)

    def test_single_page_has_no_page_indicator(self):
        entries = [_make_staff_entry(nickname="StaffA", rank=RANK.MYTH)]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        self.assertNotIn("page 1 of", embeds[0].description)

    def test_embed_uses_code_block(self):
        entries = [_make_staff_entry(nickname="StaffA", rank=RANK.MYTH)]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        self.assertIn("```", embeds[0].description)

    def test_values_formatted_with_commas(self):
        entries = [
            _make_staff_entry(nickname="RichStaff", value=1234567, rank=RANK.GOD)
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        self.assertIn("1,234,567", embeds[0].description)

    def test_description_appears_on_every_page(self):
        entries = [
            _make_staff_entry(
                nickname=f"MythPlayer{i}", rank=RANK.MYTH, value=20000 - i, discord_id=i
            )
            for i in range(15)
        ] + [
            _make_staff_entry(
                nickname=f"LegendPlayer{i}",
                rank=RANK.LEGEND,
                value=9000 - i,
                discord_id=100 + i,
            )
            for i in range(10)
        ]
        embeds = build_staff_leaderboard_embeds(entries, self.config, page_size=20)
        for embed in embeds:
            self.assertIn(self.config.description, embed.description)

    def test_empty_rank_groups_are_omitted(self):
        entries = [_make_staff_entry(nickname="MythOnly", rank=RANK.MYTH, value=14000)]
        embeds = build_staff_leaderboard_embeds(entries, self.config)
        self.assertNotIn("Legend", embeds[0].description)
        self.assertNotIn("Dragon", embeds[0].description)


if __name__ == "__main__":
    unittest.main()
