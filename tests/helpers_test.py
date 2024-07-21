import logging
import unittest
from unittest.mock import Mock

import discord

from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_member_by_nickname,
    normalize_discord_string,
    validate_member_has_role,
    validate_playername,
    validate_protected_request,
    validate_user_request,
)
from ironforgedbot.common.roles import ROLES


class TestHelpers(unittest.TestCase):
    logging.disable(logging.CRITICAL)

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

    def test_validate_user_request(self):
        """Test validate user request happy path"""
        interaction = Mock(discord.Interaction)
        guild = Mock(discord.Guild)
        member = Mock(discord.Member)
        member.name = "tester"
        member.display_name = member.name
        member.nick = member.name
        guild.members = [member]
        interaction.guild = guild
        interaction.is_expired.return_value = False

        self.assertEqual(
            validate_user_request(interaction, member.name), (member, member.name)
        )

    def test_validate_user_request_fails_when_no_guild(self):
        """Test validate user request fails when unable to access guild"""
        interaction = Mock()
        interaction.guild = None

        with self.assertRaises(ReferenceError) as context:
            validate_user_request(interaction, "")

        self.assertEqual(str(context.exception), "Error accessing server")

    def test_validate_user_request_fails_when_interaction_expired(self):
        """Test validate user request fails when interaction has expired"""
        interaction = Mock()
        interaction.guild = Mock()
        interaction.is_expired = Mock()
        interaction.is_expired.return_value = True

        with self.assertRaises(ReferenceError) as context:
            validate_user_request(interaction, "")

        self.assertEqual(str(context.exception), "Interaction has expired")

    def test_validate_protected_request(self):
        """Test validate protected request happy path"""
        interaction = Mock(discord.Interaction)
        guild = Mock(discord.Guild)
        role = Mock(discord.Role)
        role.name = ROLES.LEADERSHIP
        member = Mock(discord.Member)
        member.name = "tester"
        member.display_name = member.name
        member.nick = member.name
        member.roles = [role]
        guild.members = [member]
        interaction.user = member
        interaction.guild = guild
        interaction.is_expired.return_value = False

        self.assertEqual(
            validate_protected_request(interaction, member.name, ROLES.LEADERSHIP),
            (member, member.name),
        )

    def test_validate_protected_request_fails_no_role(self):
        """Test validate protected request fails when member does not have required role"""
        interaction = Mock(discord.Interaction)
        guild = Mock(discord.Guild)
        member = Mock(discord.Member)
        member.name = "tester"
        member.display_name = member.name
        member.nick = member.name
        member.roles = []
        guild.members = [member]
        interaction.user = member
        interaction.guild = guild
        interaction.is_expired.return_value = False

        with self.assertRaises(ValueError) as context:
            validate_protected_request(interaction, member.name, "leadership")

        self.assertEqual(
            str(context.exception),
            f"Member '{member.name}' does not have permission for this action",
        )

    def test_validate_playername(self):
        """Test validate playername happy path"""
        self.assertEqual(validate_playername("a"), "a")
        self.assertEqual(validate_playername("abcde"), "abcde")
        self.assertEqual(validate_playername("123456789012"), "123456789012")

    def test_validate_playername_fails_too_short(self):
        """Test validate playername fails when too short"""
        with self.assertRaises(ValueError) as context:
            validate_playername("")

        self.assertEqual(str(context.exception), "RSN can only be 1-12 characters long")

    def test_validate_playername_fails_too_long(self):
        """Test validate playername fails when too long"""
        with self.assertRaises(ValueError) as context:
            validate_playername("1234567890123")

        self.assertEqual(str(context.exception), "RSN can only be 1-12 characters long")

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
