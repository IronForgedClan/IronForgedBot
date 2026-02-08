import unittest
from unittest.mock import Mock

import discord

from ironforgedbot.common.roles import (
    ROLE,
    BANNED_ROLE_NAME,
    BOOSTER_ROLE_NAME,
    PROSPECT_ROLE_NAME,
    BLACKLISTED_ROLE_NAME,
    check_member_has_role,
    get_highest_privilage_role_from_member,
    member_has_any_roles,
    is_member_banned_by_role,
    has_prospect_role,
    has_booster_role,
    has_blacklisted_role,
    get_member_flags_from_discord,
    get_flag_changes,
)
from tests.helpers import (
    create_test_member,
    create_mock_discord_role,
    create_test_db_member,
)


class TestRoles(unittest.TestCase):
    def setUp(self):
        self.mock_member = Mock(spec=discord.Member)

    def test_role_or_higher(self):
        expected = ["Leadership", "Marshal", "Owners"]
        result = ROLE.LEADERSHIP.or_higher()
        self.assertEqual(expected, result)

    def test_role_or_lower(self):
        expected = ["Guest", "Applicant", "Member"]
        result = ROLE.MEMBER.or_lower()
        self.assertEqual(expected, result)

    def test_role_list(self):
        expected = [
            "Guest",
            "Applicant",
            "Member",
            "Moderator",
            "Staff",
            "Brigadier",
            "Admiral",
            "Leadership",
            "Marshal",
            "Owners",
        ]
        result = ROLE.list()
        self.assertEqual(expected, result)

    def test_role_any(self):
        result = ROLE.any()
        self.assertEqual(len(result), 10)
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
        result = get_highest_privilage_role_from_member(self.mock_member)
        self.assertEqual(result, ROLE.MEMBER)

    def test_member_has_any_roles_success(self):
        self.mock_member.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role("Staff"),
        ]
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

    def test_is_member_banned_by_role_true(self):
        self.mock_member.roles = [create_mock_discord_role("Slag")]
        result = is_member_banned_by_role(self.mock_member)
        self.assertTrue(result)

    def test_is_member_banned_by_role_false(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = is_member_banned_by_role(self.mock_member)
        self.assertFalse(result)

    def test_is_member_banned_by_role_none_member_raises_exception(self):
        with self.assertRaises(Exception):
            is_member_banned_by_role(None)

    def test_has_prospect_role_true(self):
        self.mock_member.roles = [create_mock_discord_role("Prospect")]
        result = has_prospect_role(self.mock_member)
        self.assertTrue(result)

    def test_has_prospect_role_false(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = has_prospect_role(self.mock_member)
        self.assertFalse(result)

    def test_has_booster_role_true(self):
        self.mock_member.roles = [create_mock_discord_role("Server Booster")]
        result = has_booster_role(self.mock_member)
        self.assertTrue(result)

    def test_has_booster_role_false(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = has_booster_role(self.mock_member)
        self.assertFalse(result)

    def test_has_blacklisted_role_true(self):
        self.mock_member.roles = [create_mock_discord_role("Blacklisted")]
        result = has_blacklisted_role(self.mock_member)
        self.assertTrue(result)

    def test_has_blacklisted_role_false(self):
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = has_blacklisted_role(self.mock_member)
        self.assertFalse(result)

    def test_check_member_has_role_multiple_roles(self):
        self.mock_member.roles = [
            create_mock_discord_role("Guest"),
            create_mock_discord_role("Member"),
            create_mock_discord_role("Staff"),
        ]
        result = check_member_has_role(self.mock_member, ROLE.STAFF)
        self.assertTrue(result)

    def test_role_enum_values(self):
        self.assertEqual(ROLE.GUEST, "Guest")
        self.assertEqual(ROLE.MEMBER, "Member")
        self.assertEqual(ROLE.LEADERSHIP, "Leadership")

    def test_banned_role_name_constant(self):
        self.assertEqual(BANNED_ROLE_NAME, "Slag")

    def test_get_member_flags_from_discord_no_flags(self):
        """Member with no flag roles returns all False."""
        self.mock_member.roles = [create_mock_discord_role("Member")]
        result = get_member_flags_from_discord(self.mock_member)
        self.assertEqual(
            result,
            {
                "is_booster": False,
                "is_prospect": False,
                "is_blacklisted": False,
                "is_banned": False,
            },
        )

    def test_get_member_flags_from_discord_all_flags(self):
        """Member with all flag roles returns all True."""
        self.mock_member.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role(BOOSTER_ROLE_NAME),
            create_mock_discord_role(PROSPECT_ROLE_NAME),
            create_mock_discord_role(BLACKLISTED_ROLE_NAME),
            create_mock_discord_role(BANNED_ROLE_NAME),
        ]
        result = get_member_flags_from_discord(self.mock_member)
        self.assertEqual(
            result,
            {
                "is_booster": True,
                "is_prospect": True,
                "is_blacklisted": True,
                "is_banned": True,
            },
        )

    def test_get_member_flags_from_discord_partial_flags(self):
        """Member with some flag roles returns correct values."""
        self.mock_member.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role(BOOSTER_ROLE_NAME),
            create_mock_discord_role(BANNED_ROLE_NAME),
        ]
        result = get_member_flags_from_discord(self.mock_member)
        self.assertEqual(
            result,
            {
                "is_booster": True,
                "is_prospect": False,
                "is_blacklisted": False,
                "is_banned": True,
            },
        )

    def test_get_flag_changes_no_changes(self):
        """No changes when DB and Discord flags match."""
        db_member = create_test_db_member(
            is_booster=False, is_prospect=False, is_blacklisted=False, is_banned=False
        )
        discord_flags = {
            "is_booster": False,
            "is_prospect": False,
            "is_blacklisted": False,
            "is_banned": False,
        }
        result = get_flag_changes(db_member, discord_flags)
        self.assertEqual(result, [])

    def test_get_flag_changes_single_change(self):
        """Single flag change is detected."""
        db_member = create_test_db_member(
            is_booster=False, is_prospect=False, is_blacklisted=False, is_banned=False
        )
        discord_flags = {
            "is_booster": True,
            "is_prospect": False,
            "is_blacklisted": False,
            "is_banned": False,
        }
        result = get_flag_changes(db_member, discord_flags)
        self.assertEqual(result, ["Booster: True"])

    def test_get_flag_changes_multiple_changes(self):
        """Multiple flag changes are detected."""
        db_member = create_test_db_member(
            is_booster=True, is_prospect=False, is_blacklisted=False, is_banned=True
        )
        discord_flags = {
            "is_booster": False,
            "is_prospect": True,
            "is_blacklisted": False,
            "is_banned": False,
        }
        result = get_flag_changes(db_member, discord_flags)
        self.assertEqual(len(result), 3)
        self.assertIn("Booster: False", result)
        self.assertIn("Prospect: True", result)
        self.assertIn("Banned: False", result)

    def test_get_flag_changes_all_changes(self):
        """All flags changing is detected."""
        db_member = create_test_db_member(
            is_booster=False, is_prospect=False, is_blacklisted=False, is_banned=False
        )
        discord_flags = {
            "is_booster": True,
            "is_prospect": True,
            "is_blacklisted": True,
            "is_banned": True,
        }
        result = get_flag_changes(db_member, discord_flags)
        self.assertEqual(len(result), 4)
        self.assertIn("Booster: True", result)
        self.assertIn("Prospect: True", result)
        self.assertIn("Blacklisted: True", result)
        self.assertIn("Banned: True", result)
