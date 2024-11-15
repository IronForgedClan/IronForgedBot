import unittest

from ironforgedbot.common.roles import ROLE, is_member, is_prospect
from tests.helpers import create_test_member


class TestRoles(unittest.TestCase):
    def test_role_or_higher(self):
        expected = [ROLE.DISCORD_TEAM, ROLE.LEADERSHIP]
        result = ROLE.DISCORD_TEAM.or_higher()

        self.assertEqual(expected, result)

    def test_role_or_lower(self):
        expected = [ROLE.PROSPECT, ROLE.MEMBER]
        result = ROLE.MEMBER.or_lower()

        self.assertEqual(expected, result)

    def test_is_prospect(self):
        prospect_member = create_test_member("test", ["Member", ROLE.PROSPECT])
        member = create_test_member("test", ["Member", ROLE.LEADERSHIP, "Tester"])
        self.assertEqual(is_prospect(prospect_member), True)
        self.assertEqual(is_prospect(member), False)

    def test_is_member(self):
        member = create_test_member("test", ["Tester", ROLE.MEMBER])
        non_member = create_test_member("test", ["Tester", "Foo", "Bar"])
        self.assertEqual(is_member(member), True)
        self.assertEqual(is_member(non_member), False)
