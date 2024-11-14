import unittest
from unittest.mock import patch

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)

with patch(
    "ironforgedbot.decorators.require_role",
    mock_require_role,
):
    from ironforgedbot.commands.admin.cmd_get_role_members import cmd_get_role_members


class TestGetRoleMembers(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_get_role_members(self, mock_discord_file):
        """Test get role members returns successfully"""
        caller = create_test_member("leader", ROLE.LEADERSHIP)
        member1 = create_test_member("member1", ROLE.MEMBER)
        member2 = create_test_member("member2", ROLE.MEMBER)
        member3 = create_test_member("member3", ROLE.PROSPECT)
        member4 = create_test_member("member4", ROLE.DISCORD_TEAM)

        interaction = create_mock_discord_interaction(
            user=caller, members=[caller, member1, member2, member3, member4]
        )

        await cmd_get_role_members(interaction, ROLE.MEMBER)

        expected_content = f"{member1.display_name}, {member2.display_name}"

        _, call_kwargs = mock_discord_file.call_args

        # Extract BytesIO object passed to discord.File
        file_arg = call_kwargs.get("fp")

        # Ensure the file arg exists
        self.assertIsNotNone(
            file_arg, "Expected discord.File to be called with a file-like object"
        )

        file_arg.seek(0)
        actual_content = file_arg.read()
        self.assertEqual(actual_content, expected_content.encode("utf-8"))

        followup_text = interaction.followup.send.call_args[0][0]
        self.assertEqual(
            followup_text,
            "## Member Role List\nFound **2** members with the role '**Member**'.",
        )

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_get_role_members_multiple_word_role(self, mock_discord_file):
        """Test get role members works with complex role names"""
        custom_role = "N0w this_is A rOLe!"
        caller = create_test_member("leader", ROLE.LEADERSHIP)
        member1 = create_test_member("member1", custom_role)
        member2 = create_test_member("member2", custom_role)
        member3 = create_test_member("member3", ROLE.PROSPECT)
        member4 = create_test_member("member4", custom_role)

        interaction = create_mock_discord_interaction(
            user=caller, members=[caller, member1, member2, member3, member4]
        )

        await cmd_get_role_members(interaction, custom_role)

        expected_content = (
            f"{member1.display_name}, {member2.display_name}, {member4.display_name}"
        )

        _, call_kwargs = mock_discord_file.call_args

        # Extract BytesIO object passed to discord.File
        file_arg = call_kwargs.get("fp")

        # Ensure the file arg exists
        self.assertIsNotNone(
            file_arg, "Expected discord.File to be called with a file-like object"
        )

        file_arg.seek(0)
        actual_content = file_arg.read()
        self.assertEqual(actual_content, expected_content.encode("utf-8"))

        followup_text = interaction.followup.send.call_args[0][0]
        self.assertEqual(
            followup_text,
            f"## Member Role List\nFound **3** members with the role '**{custom_role}**'.",
        )

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_get_role_members_handles_emoji(self, mock_discord_file):
        """Test get role members works with emojis in user names, roles are only ever plaintext"""
        custom_role = "alien"
        caller = create_test_member("leader", ROLE.LEADERSHIP)
        member1 = create_test_member("member1 💩", custom_role)
        member2 = create_test_member("🤖member2", custom_role)
        member3 = create_test_member("member3", ROLE.PROSPECT)
        member4 = create_test_member("member4🐼", custom_role)

        interaction = create_mock_discord_interaction(
            user=caller, members=[caller, member1, member2, member3, member4]
        )

        await cmd_get_role_members(interaction, custom_role)

        expected_content = "member1, member2, member4"

        _, call_kwargs = mock_discord_file.call_args

        # Extract BytesIO object passed to discord.File
        file_arg = call_kwargs.get("fp")

        # Ensure the file arg exists
        self.assertIsNotNone(
            file_arg, "Expected discord.File to be called with a file-like object"
        )

        file_arg.seek(0)
        actual_content = file_arg.read()
        self.assertEqual(actual_content, expected_content.encode("utf-8"))

        followup_text = interaction.followup.send.call_args[0][0]
        self.assertEqual(
            followup_text,
            "## Member Role List\nFound **3** members with the role '**alien**'.",
        )

    async def test_get_role_members_reports_none_found(self):
        """Test get role members returns message if no matching users found"""
        caller = create_test_member("leader", ROLE.LEADERSHIP)
        member1 = create_test_member("member1", ROLE.MEMBER)
        member2 = create_test_member("member2", ROLE.MEMBER)

        interaction = create_mock_discord_interaction(
            user=caller, members=[caller, member1, member2]
        )

        await cmd_get_role_members(interaction, ROLE.PROSPECT)

        interaction.followup.send.assert_called_with(
            "No members with role '**Prospect**' found."
        )
