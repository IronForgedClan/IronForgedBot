import unittest
from datetime import datetime
from dateutil import parser
from unittest.mock import MagicMock, Mock, patch

import discord

from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_member_by_nickname,
    normalize_discord_string,
    render_percentage,
    render_relative_time,
    validate_member_has_role,
    validate_playername,
)
from ironforgedbot.common.roles import ROLES
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestHelpers(unittest.TestCase):
    def test_normalize_discord_string(self):
        """ "Test to make sure normalization strips non ascii characters"""
        self.assertEqual(normalize_discord_string(""), "")
        self.assertEqual(normalize_discord_string("abc"), "abc")
        self.assertEqual(normalize_discord_string("abc😄"), "abc")
        self.assertEqual(normalize_discord_string("😄"), "")
        self.assertEqual(
            normalize_discord_string("long_text with! symbols?$😄"),
            "long_text with! symbols?$",
        )

    def test_validate_playername(self):
        """Test validate playername happy path"""
        member = create_test_member("tester", ROLES.MEMBER, "tester")
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
        member = create_test_member(playername, ROLES.MEMBER)
        interaction = create_mock_discord_interaction([member])

        assert interaction.guild

        with self.assertRaises(ValueError) as context:
            validate_playername(interaction.guild, playername)

        self.assertEqual(str(context.exception), "RSN can only be 1-12 characters long")

    def test_validate_playername_fails_too_long(self):
        """Test validate playername fails when too long"""
        playername = "0123456789012"
        member = create_test_member(playername, ROLES.MEMBER, playername)
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
        member = create_test_member(playername, ROLES.MEMBER, playername)
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
        unrelated_member = create_test_member("tester", ROLES.MEMBER)
        interaction = create_mock_discord_interaction([unrelated_member])

        assert interaction.guild

        result_member, result_playername = validate_playername(
            interaction.guild, playername, must_be_member=False
        )

        self.assertEqual(result_member, None)
        self.assertEqual(result_playername, playername)

    def test_validate_member_has_role(self):
        """Test validate member has role happy path"""
        member = Mock(discord.Member)
        role = Mock(discord.Role)
        role.name = "tester"
        member.roles = [role]

        self.assertEqual(validate_member_has_role(member, role.name), True)

    def test_validate_member_has_role_fails(self):
        """Test validate member has role fails when member does not have role"""
        member = Mock(discord.Member)
        role = Mock(discord.Role)
        role.name = "tester"
        member.roles = []

        self.assertEqual(validate_member_has_role(member, role), False)

    def test_find_member_by_nickname(self):
        """Test find member by nickname happy path"""
        guild = Mock(discord.Guild)
        member = Mock(discord.Member)
        member.name = "tester"
        member.display_name = member.name
        member.nick = member.name
        guild.members = [member]

        result = find_member_by_nickname(guild, member.name)

        self.assertEqual(result, member)

    def test_find_member_by_nickname_fails_no_guild_members(self):
        """Test find member by nickname fails when no guild members"""
        guild = Mock(discord.Guild)
        guild.members = []

        with self.assertRaises(ReferenceError) as context:
            find_member_by_nickname(guild, "tester")

        self.assertEqual(str(context.exception), "Error accessing server members")

    def test_find_member_by_nickname_fails_no_nickname(self):
        """Test find member by nickname fails when member has no nickname set"""
        guild = Mock(discord.Guild)
        member = Mock(discord.Member)
        member.name = "tester"
        member.display_name = member.name
        member.nick = ""
        guild.members = [member]

        with self.assertRaises(ValueError) as context:
            find_member_by_nickname(guild, member.name)

        self.assertEqual(
            str(context.exception),
            f"Member '**{member.name}**' does not have a nickname set",
        )

    def test_find_member_by_nickname_fails_not_found(self):
        """Test find member by nickname fails when member is not found"""
        target = "abc"
        guild = Mock(discord.Guild)
        member = Mock(discord.Member)
        member.name = "tester"
        member.display_name = member.name
        member.nick = member.name
        guild.members = [member]

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
        mock_datetime.now.return_value = datetime(2024, 9, 8, 10, 27, 20).astimezone()

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
