import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_member_by_nickname,
    datetime_to_discord_relative,
    normalize_discord_string,
    render_percentage,
    render_relative_time,
    validate_playername,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_mock_discord_guild,
    setup_time_mocks,
)


class TestHelpers(unittest.TestCase):
    def create_guild_with_member(self, member_name, nickname=None, roles=None):
        """Helper to create a guild with a single member for testing."""
        if roles is None:
            roles = [ROLE.MEMBER]
        member = create_test_member(member_name, roles, nickname)
        guild = create_mock_discord_guild([member])
        return guild, member

    def test_normalize_discord_string(self):
        """ "Test to make sure normalization strips non ascii characters"""
        self.assertEqual(normalize_discord_string(""), "")
        self.assertEqual(normalize_discord_string("abc"), "abc")
        self.assertEqual(normalize_discord_string("abc😄"), "abc")
        self.assertEqual(normalize_discord_string("😄"), "")
        self.assertEqual(normalize_discord_string("😄").encode("utf-8"), b"")
        self.assertEqual(
            normalize_discord_string("long_text with! symbols?$😄"),
            "long_text with! symbols?$",
        )

    def test_validate_playername(self):
        """Test validate playername happy path"""
        member = create_test_member("tester", [ROLE.MEMBER], "tester")
        interaction = create_mock_discord_interaction([member])

        assert interaction.guild

        result_member, result_playername = validate_playername(
            interaction.guild, member.display_name
        )

        self.assertEqual(result_member, member)
        self.assertEqual(result_playername, member.display_name)

    def test_validate_playername_fails_too_short(self):
        """Test validate playername fails when too short"""
        playername = ""
        member = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction([member])

        assert interaction.guild

        with self.assertRaises(ValueError) as context:
            validate_playername(interaction.guild, playername)

        self.assertEqual(str(context.exception), "RSN can only be 1-12 characters long")

    def test_validate_playername_fails_too_long(self):
        """Test validate playername fails when too long"""
        playername = "0123456789012"
        member = create_test_member(playername, [ROLE.MEMBER], playername)
        interaction = create_mock_discord_interaction([member])

        assert interaction.guild

        with self.assertRaises(ValueError) as context:
            validate_playername(interaction.guild, playername)

        self.assertEqual(str(context.exception), "RSN can only be 1-12 characters long")

    def test_validate_playername_optional_member_returns_member_object_if_found(self):
        """
        Test that when validating playername where must_be_member is False.
        It should still attempt to fetch and return Member object if possible
        """
        playername = "player"
        member = create_test_member(playername, [ROLE.MEMBER], playername)
        interaction = create_mock_discord_interaction([member])

        assert interaction.guild

        result_member, result_playername = validate_playername(
            interaction.guild, member.display_name, must_be_member=False
        )

        self.assertEqual(result_member, member)
        self.assertEqual(result_playername, member.display_name)

    def test_validate_playername_optional_member_returns_null_member_obj(self):
        """
        Test that when validating playername where must_be_member is False.
        It should return None in place of Member object if not found
        """
        playername = "player"
        unrelated_member = create_test_member("tester", [ROLE.MEMBER])
        interaction = create_mock_discord_interaction([unrelated_member])

        assert interaction.guild

        result_member, result_playername = validate_playername(
            interaction.guild, playername, must_be_member=False
        )

        self.assertEqual(result_member, None)
        self.assertEqual(result_playername, playername)

    def test_find_member_by_nickname(self):
        """Test find member by nickname happy path"""
        member = create_test_member("tester", [ROLE.MEMBER], "tester")
        guild = create_mock_discord_guild([member])

        result = find_member_by_nickname(guild, member.display_name)

        self.assertEqual(result, member)

    def test_find_member_by_nickname_fails_no_guild_members(self):
        """Test find member by nickname fails when no guild members"""
        guild = create_mock_discord_guild([])  # No members

        with self.assertRaises(ReferenceError) as context:
            find_member_by_nickname(guild, "tester")

        self.assertEqual(str(context.exception), "Error accessing server members")

    def test_find_member_by_nickname_fails_no_nickname(self):
        """Test find member by nickname fails when member has no nickname set"""
        member = create_test_member("tester", [ROLE.MEMBER])  # No nickname set
        member.nick = ""  # Explicitly clear nickname
        guild = create_mock_discord_guild([member])

        with self.assertRaises(ValueError) as context:
            find_member_by_nickname(guild, member.name)

        self.assertEqual(
            str(context.exception),
            f"Member '**{member.name}**' does not have a nickname set",
        )

    def test_find_member_by_nickname_fails_not_found(self):
        """Test find member by nickname fails when member is not found"""
        target = "abc"
        member = create_test_member("tester", [ROLE.MEMBER], "tester")
        guild = create_mock_discord_guild([member])

        with self.assertRaises(ValueError) as context:
            find_member_by_nickname(guild, target)

        self.assertEqual(
            str(context.exception),
            f"Player '**{target}**' is not a member of this server",
        )

    def test_calculate_percentage(self):
        """Test caluclate percentage is correct"""
        self.assertEqual(calculate_percentage(10, 100), 10)
        self.assertEqual(calculate_percentage(50, 100), 50)
        self.assertEqual(calculate_percentage(0, 100), 0)
        self.assertEqual(calculate_percentage(12.5, 100), 12.5)
        self.assertEqual(calculate_percentage(0, 0), 0)
        self.assertEqual(calculate_percentage(1, 0), 100)
        self.assertEqual(calculate_percentage(0, 1), 0)

    def test_render_percentage(self):
        """Test rendering percentage is correct"""
        self.assertEqual(render_percentage(10, 100), "10%")
        self.assertEqual(render_percentage(50, 100), "50%")
        self.assertEqual(render_percentage(0, 100), "<1%")
        self.assertEqual(render_percentage(12.6, 100), "13%")
        self.assertEqual(render_percentage(12.4, 100), "12%")
        self.assertEqual(render_percentage(99.9, 100), ">99%")

    @patch("ironforgedbot.common.helpers.datetime")
    def test_render_relative_time(self, mock_datetime):
        """Test rendering of relative time is correct"""
        fixed_now = setup_time_mocks(
            mock_datetime,
            None,
            fixed_datetime=datetime(2024, 9, 8, 10, 27, 20).astimezone(),
        )

        self.assertEqual(
            render_relative_time(datetime(2024, 9, 8, 10, 27, 19).astimezone()),
            "1 second ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 8, 10, 27, 0).astimezone()),
            "20 seconds ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 8, 10, 26, 0).astimezone()),
            "1 minute ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 8, 10, 20, 0).astimezone()),
            "7 minutes ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 8, 9, 26, 25).astimezone()),
            "1 hour ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 8, 1, 26, 25).astimezone()),
            "9 hours ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 7, 9, 26, 25).astimezone()),
            "1 day ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 5, 9, 26, 25).astimezone()),
            "3 days ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 9, 1, 9, 26, 25).astimezone()),
            "1 week ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 8, 15, 9, 26, 25).astimezone()),
            "3 weeks ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 8, 7, 9, 26, 25).astimezone()),
            "1 month ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2024, 3, 7, 9, 26, 25).astimezone()),
            "6 months ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2023, 8, 7, 9, 26, 25).astimezone()),
            "1 year ago",
        )
        self.assertEqual(
            render_relative_time(datetime(2000, 8, 7, 9, 26, 25).astimezone()),
            "24 years ago",
        )

    def test_datetime_to_discord_relative(self):
        """Test conversion of iso timestamp to Discord's relative time format"""
        self.assertEqual(
            datetime_to_discord_relative(
                datetime.fromisoformat("2025-01-20T21:31:01Z")
            ),
            "<t:1737408661:d>",
        )
        self.assertEqual(
            datetime_to_discord_relative(
                datetime.fromisoformat("2025-01-20T21:31:01+00:00")
            ),
            "<t:1737408661:d>",
        )
        self.assertEqual(
            datetime_to_discord_relative(
                datetime.fromisoformat("2025-01-20T21:31:01+00:00"), "r"
            ),
            "<t:1737408661:r>",
        )
        self.assertEqual(
            datetime_to_discord_relative(
                datetime.fromisoformat("2025-01-20T21:31:01+01:00")
            ),
            "<t:1737405061:d>",
        )

    def test_normalize_discord_string_edge_cases(self):
        """Test normalize_discord_string with additional edge cases"""
        self.assertEqual(normalize_discord_string("abc def"), "abc def")
        self.assertEqual(
            normalize_discord_string("  spaces  "), "spaces"
        )  # Strips leading/trailing spaces
        self.assertEqual(
            normalize_discord_string("multiple   spaces"), "multiple spaces"
        )  # Normalizes multiple spaces
        self.assertEqual(normalize_discord_string("123numbers"), "123numbers")
        self.assertEqual(normalize_discord_string("special!@#$%"), "special!@#$%")

    def test_calculate_percentage_edge_cases(self):
        """Test calculate_percentage with additional edge cases"""
        # Test with floating point precision
        self.assertEqual(calculate_percentage(1, 3), 33.333333333333336)
        self.assertEqual(calculate_percentage(2, 3), 66.66666666666667)

        # Test with very small numbers
        self.assertEqual(calculate_percentage(0.1, 1000), 0.01)
        self.assertEqual(calculate_percentage(1, 10000), 0.01)

    def test_render_percentage_edge_cases(self):
        """Test render_percentage with additional edge cases"""
        # Test boundary conditions around <1% and >99%
        self.assertEqual(render_percentage(0.1, 100), "<1%")
        self.assertEqual(render_percentage(0.9, 100), "<1%")
        self.assertEqual(render_percentage(1.0, 100), "1%")
        self.assertEqual(render_percentage(99.0, 100), "99%")
        self.assertEqual(render_percentage(99.5, 100), ">99%")
        self.assertEqual(render_percentage(100, 100), ">99%")

    def test_validate_playername_case_sensitivity(self):
        """Test validate_playername handles case sensitivity correctly"""
        guild, member = self.create_guild_with_member("TestUser", "testuser")

        # Should find member regardless of case
        result_member, result_playername = validate_playername(guild, "TestUser")
        self.assertEqual(result_member, member)
        self.assertEqual(result_playername, "TestUser")

    def test_find_member_by_nickname_case_variations(self):
        """Test find_member_by_nickname with different case variations"""
        guild, member = self.create_guild_with_member("TestUser", "testuser")

        # Should find member by exact nickname match
        result = find_member_by_nickname(guild, "testuser")
        self.assertEqual(result, member)
