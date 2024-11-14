import unittest

from ironforgedbot.common.roles import ROLE, is_member, is_prospect


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
        self.assertEqual(is_prospect(["Member", ROLE.PROSPECT]), True)
        self.assertEqual(is_prospect([ROLE.PROSPECT]), True)
        self.assertEqual(is_prospect(["bar", ROLE.PROSPECT, "foo"]), True)
        self.assertEqual(is_prospect(["Member"]), False)
        self.assertEqual(is_prospect(["Member", "foo", "bar"]), False)

    def test_is_member(self):
        self.assertEqual(is_member([ROLE.MEMBER, "foo"]), True)
        self.assertEqual(is_member(["bar", ROLE.MEMBER, "foo"]), True)
        self.assertEqual(is_member(["bar", "foo"]), False)
