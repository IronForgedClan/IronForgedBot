import unittest
from unittest.mock import patch

from ironforgedbot.common.roles import ROLES
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
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        member1 = create_test_member("member1", ROLES.MEMBER)
        member2 = create_test_member("member2", ROLES.MEMBER)
        member3 = create_test_member("member3", ROLES.PROSPECT)
        member4 = create_test_member("member4", ROLES.DISCORD_TEAM)

        interaction = create_mock_discord_interaction(
            user=caller, members=[caller, member1, member2, member3, member4]
        )

        await cmd_get_role_members(interaction, ROLES.MEMBER)

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
            f"## Member Role List\nFound **2** members with the role '**{ROLES.MEMBER}**'.",
        )

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_get_role_members_multiple_word_role(self, mock_discord_file):
        custom_role = "N0w this_is A rOLe!"
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        member1 = create_test_member("member1", custom_role)
        member2 = create_test_member("member2", custom_role)
        member3 = create_test_member("member3", ROLES.PROSPECT)
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
        custom_role = "alien"
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        member1 = create_test_member("member1 💩", custom_role)
        member2 = create_test_member("🤖member2", custom_role)
        member3 = create_test_member("member3", ROLES.PROSPECT)
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
            f"## Member Role List\nFound **3** members with the role '**{custom_role}**'.",
        )

    async def test_get_role_members_reports_none_found(self):
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        member1 = create_test_member("member1", ROLES.MEMBER)
        member2 = create_test_member("member2", ROLES.MEMBER)

        interaction = create_mock_discord_interaction(
            user=caller, members=[caller, member1, member2]
        )

        await cmd_get_role_members(interaction, ROLES.PROSPECT)

        interaction.followup.send.assert_called_with(
            f"No members with role '**{ROLES.PROSPECT}**' found."
        )
