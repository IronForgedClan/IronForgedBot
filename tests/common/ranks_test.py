import unittest

from ironforgedbot.common.ranks import RANK, GOD_ALIGNMENT, get_rank_from_member
from tests.helpers import create_test_member


class TestGetRankFromMember(unittest.TestCase):
    def test_returns_none_for_none_member(self):
        result = get_rank_from_member(None)
        self.assertIsNone(result)

    def test_returns_none_for_no_rank_roles(self):
        member = create_test_member("user", ["Member", "Staff"])
        result = get_rank_from_member(member)
        self.assertIsNone(result)

    def test_returns_single_rank(self):
        member = create_test_member("user", ["Member", "Rune"])
        result = get_rank_from_member(member)
        self.assertEqual(result, RANK.RUNE)

    def test_returns_highest_rank_with_multiple(self):
        member = create_test_member("user", ["Member", "Iron", "Dragon"])
        result = get_rank_from_member(member)
        self.assertEqual(result, RANK.DRAGON)

    def test_returns_god_alignment_when_god_rank(self):
        member = create_test_member("user", ["Member", "God", "Saradominist"])
        result = get_rank_from_member(member)
        self.assertEqual(result, GOD_ALIGNMENT.SARADOMIN)

    def test_returns_god_when_no_alignment(self):
        member = create_test_member("user", ["Member", "God"])
        result = get_rank_from_member(member)
        self.assertEqual(result, RANK.GOD)
