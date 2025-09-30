import unittest
from unittest.mock import Mock

from ironforgedbot.common.autocompletes import role_autocomplete
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestAutocompletes(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        mock_member = create_test_member("TestUser", [])
        mock_member.id = 123456789
        self.mock_interaction = create_mock_discord_interaction(user=mock_member)

    async def test_role_autocomplete_filters_and_sorts_roles(self):
        # Create mock roles with different positions
        role1 = Mock()
        role1.name = "Member"
        role1.position = 10
        role1.is_bot_managed.return_value = False

        role2 = Mock()
        role2.name = "Leadership"
        role2.position = 20
        role2.is_bot_managed.return_value = False

        role3 = Mock()
        role3.name = "Bot Role"
        role3.position = 5
        role3.is_bot_managed.return_value = True  # Should be filtered out

        role4 = Mock()
        role4.name = "Staff Member"
        role4.position = 15
        role4.is_bot_managed.return_value = False

        everyone_role = Mock()
        everyone_role.name = "@everyone"
        everyone_role.position = 0

        self.mock_interaction.guild.roles = [role1, role2, role3, role4, everyone_role]
        self.mock_interaction.guild.default_role = everyone_role

        # Test filtering by input "member"
        choices = await role_autocomplete(self.mock_interaction, "member")

        # Should return Staff Member and Member, sorted by position (Staff Member first)
        self.assertEqual(len(choices), 2)
        self.assertEqual(choices[0].name, "Staff Member")  # Higher position
        self.assertEqual(choices[0].value, "Staff Member")
        self.assertEqual(choices[1].name, "Member")  # Lower position
        self.assertEqual(choices[1].value, "Member")

    async def test_role_autocomplete_empty_guild(self):
        self.mock_interaction.guild = None

        choices = await role_autocomplete(self.mock_interaction, "test")

        self.assertEqual(choices, [])

    async def test_role_autocomplete_no_matches(self):
        role1 = Mock()
        role1.name = "Member"
        role1.is_bot_managed.return_value = False

        everyone_role = Mock()
        everyone_role.name = "@everyone"

        self.mock_interaction.guild.roles = [role1, everyone_role]
        self.mock_interaction.guild.default_role = everyone_role

        choices = await role_autocomplete(self.mock_interaction, "xyz")

        self.assertEqual(choices, [])

    async def test_role_autocomplete_case_insensitive_filtering(self):
        role1 = Mock()
        role1.name = "TestRole"
        role1.position = 10
        role1.is_bot_managed.return_value = False

        everyone_role = Mock()
        everyone_role.name = "@everyone"
        everyone_role.position = 0

        self.mock_interaction.guild.roles = [role1, everyone_role]
        self.mock_interaction.guild.default_role = everyone_role

        # Test case insensitive matching
        choices = await role_autocomplete(self.mock_interaction, "TEST")

        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].name, "TestRole")
        self.assertEqual(choices[0].value, "TestRole")

    async def test_role_autocomplete_excludes_everyone_role(self):
        role1 = Mock()
        role1.name = "TestRole"
        role1.position = 10
        role1.is_bot_managed.return_value = False

        everyone_role = Mock()
        everyone_role.name = "@everyone"
        everyone_role.position = 0

        self.mock_interaction.guild.roles = [role1, everyone_role]
        self.mock_interaction.guild.default_role = everyone_role

        choices = await role_autocomplete(self.mock_interaction, "")

        # Should only return TestRole, not @everyone
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].name, "TestRole")

    async def test_role_autocomplete_excludes_bot_managed_roles(self):
        role1 = Mock()
        role1.name = "NormalRole"
        role1.position = 10
        role1.is_bot_managed.return_value = False

        bot_role = Mock()
        bot_role.name = "BotRole"
        bot_role.position = 15
        bot_role.is_bot_managed.return_value = True

        everyone_role = Mock()
        everyone_role.name = "@everyone"
        everyone_role.position = 0

        self.mock_interaction.guild.roles = [role1, bot_role, everyone_role]
        self.mock_interaction.guild.default_role = everyone_role

        choices = await role_autocomplete(self.mock_interaction, "role")

        # Should only return NormalRole, not BotRole
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].name, "NormalRole")

    async def test_role_autocomplete_limits_to_25_results(self):
        roles = []
        for i in range(30):  # Create 30 roles
            role = Mock()
            role.name = f"Role{i:02d}"
            role.position = i
            role.is_bot_managed.return_value = False
            roles.append(role)

        everyone_role = Mock()
        everyone_role.name = "@everyone"
        everyone_role.position = 0
        roles.append(everyone_role)

        self.mock_interaction.guild.roles = roles
        self.mock_interaction.guild.default_role = everyone_role

        choices = await role_autocomplete(self.mock_interaction, "role")

        # Should be limited to 25 results
        self.assertEqual(len(choices), 25)
        # Should be sorted by position (highest first)
        self.assertEqual(choices[0].name, "Role29")  # Highest position
        self.assertEqual(choices[24].name, "Role05")  # 25th highest position


class TestMemberNicknameAutocomplete(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        mock_member = create_test_member("TestUser", [])
        mock_member.id = 123456789
        self.mock_interaction = create_mock_discord_interaction(user=mock_member)

    def create_member_with_nickname(self, display_name, nickname):
        member = Mock()
        member.display_name = display_name
        member.nick = nickname
        return member

    async def test_member_nickname_autocomplete_filters_by_input(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        member1 = self.create_member_with_nickname("PlayerOne", "PlayerOne")
        member2 = self.create_member_with_nickname("PlayerTwo", "PlayerTwo")
        member3 = self.create_member_with_nickname("TestPlayer", "TestPlayer")

        self.mock_interaction.guild.members = [member1, member2, member3]

        choices = await member_nickname_autocomplete(self.mock_interaction, "player")

        # Should return all members with "player" in their name
        self.assertEqual(len(choices), 3)
        choice_names = [choice.name for choice in choices]
        self.assertIn("PlayerOne", choice_names)
        self.assertIn("PlayerTwo", choice_names)
        self.assertIn("TestPlayer", choice_names)

    async def test_member_nickname_autocomplete_case_insensitive(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        member1 = self.create_member_with_nickname("TestUser", "TestUser")
        member2 = self.create_member_with_nickname("testplayer", "testplayer")

        self.mock_interaction.guild.members = [member1, member2]

        choices = await member_nickname_autocomplete(self.mock_interaction, "TEST")

        self.assertEqual(len(choices), 2)
        choice_names = [choice.name for choice in choices]
        self.assertIn("TestUser", choice_names)
        self.assertIn("testplayer", choice_names)

    async def test_member_nickname_autocomplete_excludes_no_nickname(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        # Members without nicknames
        member1 = Mock()
        member1.display_name = "NoNickUser"
        member1.nick = None

        member2 = Mock()
        member2.display_name = "EmptyNickUser"
        member2.nick = ""

        # Member with nickname
        member3 = self.create_member_with_nickname("HasNickUser", "HasNickUser")

        self.mock_interaction.guild.members = [member1, member2, member3]

        choices = await member_nickname_autocomplete(self.mock_interaction, "user")

        # Should only return the member with a nickname
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].name, "HasNickUser")

    async def test_member_nickname_autocomplete_empty_guild(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        self.mock_interaction.guild = None

        choices = await member_nickname_autocomplete(self.mock_interaction, "test")

        self.assertEqual(choices, [])

    async def test_member_nickname_autocomplete_no_members(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        self.mock_interaction.guild.members = []

        choices = await member_nickname_autocomplete(self.mock_interaction, "test")

        self.assertEqual(choices, [])

    async def test_member_nickname_autocomplete_sorts_alphabetically(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        member1 = self.create_member_with_nickname("ZebraUser", "ZebraUser")
        member2 = self.create_member_with_nickname("AlphaUser", "AlphaUser")
        member3 = self.create_member_with_nickname("BetaUser", "BetaUser")

        self.mock_interaction.guild.members = [member1, member2, member3]

        choices = await member_nickname_autocomplete(self.mock_interaction, "user")

        # Should be sorted alphabetically
        self.assertEqual(len(choices), 3)
        self.assertEqual(choices[0].name, "AlphaUser")
        self.assertEqual(choices[1].name, "BetaUser")
        self.assertEqual(choices[2].name, "ZebraUser")

    async def test_member_nickname_autocomplete_limits_to_25_results(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        members = []
        for i in range(30):  # Create 30 members
            member = self.create_member_with_nickname(f"User{i:02d}", f"User{i:02d}")
            members.append(member)

        self.mock_interaction.guild.members = members

        choices = await member_nickname_autocomplete(self.mock_interaction, "user")

        # Should be limited to 25 results
        self.assertEqual(len(choices), 25)
        # Should be sorted alphabetically
        self.assertEqual(choices[0].name, "User00")
        self.assertEqual(choices[24].name, "User24")

    async def test_member_nickname_autocomplete_handles_emoji_normalization(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        member1 = self.create_member_with_nickname("TestUser 💩", "TestUser 💩")
        member2 = self.create_member_with_nickname("🤖TestUser", "🤖TestUser")

        self.mock_interaction.guild.members = [member1, member2]

        choices = await member_nickname_autocomplete(self.mock_interaction, "testuser")

        # Should find both members after emoji normalization
        self.assertEqual(len(choices), 2)
        choice_names = [choice.name for choice in choices]
        self.assertIn("TestUser 💩", choice_names)
        self.assertIn("🤖TestUser", choice_names)

    async def test_member_nickname_autocomplete_no_matches(self):
        from ironforgedbot.common.autocompletes import member_nickname_autocomplete

        member1 = self.create_member_with_nickname("PlayerOne", "PlayerOne")
        member2 = self.create_member_with_nickname("PlayerTwo", "PlayerTwo")

        self.mock_interaction.guild.members = [member1, member2]

        choices = await member_nickname_autocomplete(self.mock_interaction, "xyz")

        self.assertEqual(choices, [])
