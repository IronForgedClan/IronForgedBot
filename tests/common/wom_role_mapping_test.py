import unittest
from wom import GroupRole

from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.wom_role_mapping import (
    WOM_TO_DISCORD_ROLE_MAPPING,
    WOM_TO_DISCORD_RANK_MAPPING,
    get_discord_role_for_wom_role,
    get_discord_rank_for_wom_role,
    get_display_name_for_wom_role,
)
from tests.helpers import (
    validate_role_mappings,
    get_all_wom_roles_for_discord_role,
    get_all_wom_roles_for_discord_rank,
)


class TestWomRoleMapping(unittest.TestCase):
    """Test WOM to Discord role mapping functionality."""

    def test_get_discord_role_for_wom_role_mapped(self):
        """Test getting Discord role for mapped WOM role."""
        result = get_discord_role_for_wom_role(GroupRole.Iron)
        self.assertEqual(result, ROLE.MEMBER)

        result = get_discord_role_for_wom_role(GroupRole.Administrator)
        self.assertEqual(result, ROLE.LEADERSHIP)

    def test_get_discord_role_for_wom_role_unmapped(self):
        """Test getting Discord role for unmapped WOM role."""
        # Use a role that's unlikely to be mapped
        result = get_discord_role_for_wom_role(GroupRole.Wizard)
        self.assertIsNone(result)

    def test_get_discord_role_for_wom_role_none(self):
        """Test getting Discord role for None."""
        result = get_discord_role_for_wom_role(None)
        self.assertIsNone(result)

    def test_get_discord_rank_for_wom_role_mapped(self):
        """Test getting Discord rank for mapped WOM role."""
        result = get_discord_rank_for_wom_role(GroupRole.Iron)
        self.assertEqual(result, RANK.IRON)

        result = get_discord_rank_for_wom_role(GroupRole.Dragon)
        self.assertEqual(result, RANK.DRAGON)

        result = get_discord_rank_for_wom_role(GroupRole.Sage)
        self.assertEqual(result, RANK.GOD_GUTHIX)

    def test_get_discord_rank_for_wom_role_unmapped(self):
        """Test getting Discord rank for unmapped WOM role."""
        # Staff roles don't have rank mappings
        result = get_discord_rank_for_wom_role(GroupRole.Administrator)
        self.assertIsNone(result)

    def test_get_discord_rank_for_wom_role_none(self):
        """Test getting Discord rank for None."""
        result = get_discord_rank_for_wom_role(None)
        self.assertIsNone(result)

    def test_get_display_name_for_wom_role_mapped(self):
        """Test getting display name for mapped WOM role."""
        result = get_display_name_for_wom_role(GroupRole.Iron)
        self.assertEqual(result, ROLE.MEMBER.value)

        result = get_display_name_for_wom_role(GroupRole.Administrator)
        self.assertEqual(result, ROLE.LEADERSHIP.value)

    def test_get_display_name_for_wom_role_unmapped(self):
        """Test getting display name for unmapped WOM role."""
        result = get_display_name_for_wom_role(GroupRole.Wizard)
        self.assertEqual(result, "Wizard")

    def test_get_display_name_for_wom_role_none(self):
        """Test getting display name for None role."""
        result = get_display_name_for_wom_role(None)
        self.assertEqual(result, "Unknown")

    def test_get_all_wom_roles_for_discord_role(self):
        """Test getting all WOM roles for a Discord role."""
        member_roles = get_all_wom_roles_for_discord_role(ROLE.MEMBER)
        self.assertIn(GroupRole.Iron, member_roles)
        self.assertIn(GroupRole.Mithril, member_roles)
        self.assertIn(GroupRole.Adamant, member_roles)

        leadership_roles = get_all_wom_roles_for_discord_role(ROLE.LEADERSHIP)
        self.assertIn(GroupRole.Administrator, leadership_roles)
        self.assertIn(GroupRole.Owner, leadership_roles)

    def test_get_all_wom_roles_for_discord_rank(self):
        """Test getting all WOM roles for a Discord rank."""
        iron_roles = get_all_wom_roles_for_discord_rank(RANK.IRON)
        self.assertIn(GroupRole.Iron, iron_roles)

        dragon_roles = get_all_wom_roles_for_discord_rank(RANK.DRAGON)
        self.assertIn(GroupRole.Dragon, dragon_roles)

    def test_validate_role_mappings_valid(self):
        """Test validation of valid role mappings."""
        errors = validate_role_mappings()
        self.assertEqual(len(errors), 0)

    def test_critical_roles_mapped(self):
        """Test that critical WOM roles are mapped."""
        critical_roles = [
            GroupRole.Iron,
            GroupRole.Mithril,
            GroupRole.Administrator,
            GroupRole.Dogsbody,
        ]

        for role in critical_roles:
            with self.subTest(role=role):
                self.assertIn(role, WOM_TO_DISCORD_ROLE_MAPPING)


if __name__ == "__main__":
    unittest.main()
