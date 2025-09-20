import unittest
from unittest.mock import Mock

import discord

from ironforgedbot.common.roles import ROLE, check_member_has_role, get_highest_privilage_role_from_member, member_has_any_roles, is_member_banned
from tests.helpers import create_test_member, create_mock_discord_role


class TestRoles(unittest.TestCase):
    def setUp(self):
        self.mock_member = Mock(spec=discord.Member)

    def test_role_or_higher(self):
        expected = ["Discord Team", "Bot Team", "Leadership"]
        result = ROLE.DISCORD_TEAM.or_higher()
        self.assertEqual(expected, result)

    def test_role_or_lower(self):
        expected = ["Slag", "Guest", "Applicant", "Prospect", "Member"]
        result = ROLE.MEMBER.or_lower()
        self.assertEqual(expected, result)

    def test_role_list(self):
        expected = ["Slag", "Guest", "Applicant", "Prospect", "Member", "Staff", "Events Team", "Recruitment Team", "Discord Team", "Bot Team", "Leadership"]
        result = ROLE.list()
        self.assertEqual(expected, result)

    def test_role_any(self):
        result = ROLE.any()
        self.assertEqual(len(result), 11)
        self.assertIn(ROLE.MEMBER, result)
        self.assertIn(ROLE.LEADERSHIP, result)

    def test_check_member_has_role_exact_match(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = check_member_has_role(self.mock_member, ROLE.MEMBER)
        self.assertTrue(result)

    def test_check_member_has_role_no_match(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = check_member_has_role(self.mock_member, ROLE.LEADERSHIP)
        self.assertFalse(result)

    def test_check_member_has_role_case_insensitive(self):
        self.mock_member.roles = [create_mock_discord_role("member")]
        result = check_member_has_role(self.mock_member, ROLE.MEMBER)
        self.assertTrue(result)

    def test_check_member_has_role_with_whitespace(self):
        self.mock_member.roles = [create_mock_discord_role(" Member ")]
        result = check_member_has_role(self.mock_member, ROLE.MEMBER)
        self.assertTrue(result)

    def test_check_member_has_role_or_higher_success(self):
        self.mock_member.roles = [create_mock_discord_role("Leadership")]
        result = check_member_has_role(self.mock_member, ROLE.MEMBER, or_higher=True)
        self.assertTrue(result)

    def test_check_member_has_role_or_higher_fail(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = check_member_has_role(self.mock_member, ROLE.STAFF, or_higher=True)
        self.assertFalse(result)

    def test_check_member_has_role_or_lower_success(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = check_member_has_role(self.mock_member, ROLE.LEADERSHIP, or_lower=True)
        self.assertTrue(result)

    def test_check_member_has_role_or_lower_fail(self):
        self.mock_member.roles = [create_mock_discord_role("Staff")]
        result = check_member_has_role(self.mock_member, ROLE.MEMBER, or_lower=True)
        self.assertFalse(result)

    def test_check_member_has_role_empty_roles(self):
        self.mock_member.roles = []
        result = check_member_has_role(self.mock_member, ROLE.MEMBER)
        self.assertFalse(result)

    def test_get_highest_privilage_role_from_member_single_role(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        with self.assertRaises(AttributeError):
            get_highest_privilage_role_from_member(self.mock_member)

    def test_member_has_any_roles_success(self):
        self.mock_member.roles = [create_mock_discord_role("Member"), create_mock_discord_role("Staff")]
        result = member_has_any_roles(self.mock_member, [ROLE.MEMBER, ROLE.LEADERSHIP])
        self.assertTrue(result)

    def test_member_has_any_roles_fail(self):
        self.mock_member.roles = [create_mock_discord_role("Guest")]
        result = member_has_any_roles(self.mock_member, [ROLE.MEMBER, ROLE.LEADERSHIP])
        self.assertFalse(result)

    def test_member_has_any_roles_case_insensitive(self):
        self.mock_member.roles = [create_mock_discord_role("member")]
        result = member_has_any_roles(self.mock_member, [ROLE.MEMBER])
        self.assertTrue(result)

    def test_member_has_any_roles_empty_list(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = member_has_any_roles(self.mock_member, [])
        self.assertFalse(result)

    def test_is_member_banned_true(self):
        self.mock_member.roles = [create_mock_discord_role("Slag")]
        result = is_member_banned(self.mock_member)
        self.assertTrue(result)

    def test_is_member_banned_false(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = is_member_banned(self.mock_member)
        self.assertFalse(result)

    def test_is_member_banned_none_member_raises_exception(self):
        with self.assertRaises(Exception):
            is_member_banned(None)

    def test_check_member_has_role_multiple_roles(self):
        self.mock_member.roles = [
            create_mock_discord_role("Guest"),
            create_mock_discord_role("Member"),
            create_mock_discord_role("Staff")
        ]
        result = check_member_has_role(self.mock_member, ROLE.STAFF)
        self.assertTrue(result)

    def test_role_enum_values(self):
        self.assertEqual(ROLE.BANNED, "Slag")
        self.assertEqual(ROLE.GUEST, "Guest")
        self.assertEqual(ROLE.MEMBER, "Member")
        self.assertEqual(ROLE.LEADERSHIP, "Leadership")