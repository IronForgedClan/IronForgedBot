import unittest

from ironforgedbot.common.roles import ROLE, check_member_has_role
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

    def test_check_member_has_role(self):
        """Test validate member has role"""
        member = create_test_member("", [ROLE.MEMBER])
        self.assertEqual(check_member_has_role(member, ROLE.MEMBER), True)

    def test_check_member_has_role_fails(self):
        """Test validate member has role fails when member does not have role"""
        member = create_test_member("", [ROLE.MEMBER])

        self.assertEqual(check_member_has_role(member, ROLE.LEADERSHIP), False)

    def test_check_member_has_role_or_higher(self):
        """Test validate member has role or higher"""
        member = create_test_member("", [ROLE.LEADERSHIP])

        self.assertEqual(
            check_member_has_role(member, ROLE.MEMBER, or_higher=True), True
        )

    def test_check_member_has_role_or_higher_fail(self):
        """Test validate member has role or higher"""
        member = create_test_member("", [ROLE.MEMBER])

        self.assertEqual(
            check_member_has_role(member, ROLE.STAFF, or_higher=True), False
        )

    def test_check_member_has_role_or_lower(self):
        """Test validate member has role or lower"""
        member = create_test_member("", [ROLE.MEMBER])

        self.assertEqual(
            check_member_has_role(member, ROLE.LEADERSHIP, or_lower=True), True
        )

    def test_check_member_has_role_or_lower_fail(self):
        """Test validate member has role or lower"""
        member = create_test_member("", [])

        self.assertEqual(
            check_member_has_role(member, ROLE.MEMBER, or_lower=True), False
        )
