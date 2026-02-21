import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE, PROSPECT_ROLE_NAME
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestGetRoleMembers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_require_role_patcher = patch(
            "ironforgedbot.decorators.require_role.require_role"
        )
        self.mock_require_role = self.mock_require_role_patcher.start()
        self.mock_require_role.side_effect = lambda *args, **kwargs: lambda func: func

        from ironforgedbot.commands.admin.cmd_get_role_members import (
            cmd_get_role_members,
        )

        self.cmd_get_role_members = cmd_get_role_members

        mock_member = create_test_member("TestUser", [ROLE.LEADERSHIP])
        mock_member.id = 123456789
        self.mock_interaction = create_mock_discord_interaction(user=mock_member)

    def tearDown(self):
        self.mock_require_role_patcher.stop()

    def create_member(self, display_name, roles):
        member = Mock()
        member.display_name = display_name
        member.roles = []
        for role_name in roles:
            role = Mock()
            role.name = role_name
            member.roles.append(role)
        return member

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_success(self, mock_discord_file):
        member1 = self.create_member("member1", [ROLE.MEMBER])
        member2 = self.create_member("member2", [ROLE.MEMBER])
        member3 = self.create_member("member3", [PROSPECT_ROLE_NAME])

        self.mock_interaction.guild.members = [member1, member2, member3]
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await self.cmd_get_role_members(self.mock_interaction, ROLE.MEMBER)

        mock_discord_file.assert_called_once()
        call_args = mock_discord_file.call_args
        fp_arg = call_args.kwargs["fp"]
        filename_arg = call_args.kwargs["filename"]

        fp_arg.seek(0)
        content = fp_arg.read().decode("utf-8")
        self.assertEqual(content, "member1, member2")
        self.assertTrue(filename_arg.startswith("member_role_list_"))
        self.assertTrue(filename_arg.endswith(".txt"))

        self.mock_interaction.followup.send.assert_called_once()
        send_args = self.mock_interaction.followup.send.call_args
        self.assertIn("## Member Role List", send_args.args[0])
        self.assertIn("Found **2** members", send_args.args[0])
        self.assertIn("**Member**", send_args.args[0])
        self.assertEqual(send_args.kwargs["file"], mock_file)

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_custom_role(self, mock_discord_file):
        custom_role = "Custom Role Name"
        member1 = self.create_member("user1", [custom_role])
        member2 = self.create_member("user2", [ROLE.MEMBER])
        member3 = self.create_member("user3", [custom_role])

        self.mock_interaction.guild.members = [member1, member2, member3]
        mock_file = Mock()
        mock_discord_file.return_value = mock_file

        await self.cmd_get_role_members(self.mock_interaction, custom_role)

        call_args = mock_discord_file.call_args
        fp_arg = call_args.kwargs["fp"]
        filename_arg = call_args.kwargs["filename"]

        fp_arg.seek(0)
        content = fp_arg.read().decode("utf-8")
        self.assertEqual(content, "user1, user3")
        self.assertTrue(filename_arg.startswith("custom_role_name_role_list_"))

        send_args = self.mock_interaction.followup.send.call_args
        self.assertIn("Found **2** members", send_args.args[0])
        self.assertIn("**Custom Role Name**", send_args.args[0])

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_emoji_normalization(self, mock_discord_file):
        member1 = self.create_member("user1 💩", [ROLE.MEMBER])
        member2 = self.create_member("🤖user2", [ROLE.MEMBER])
        member3 = self.create_member("user3🐼", [ROLE.MEMBER])

        self.mock_interaction.guild.members = [member1, member2, member3]

        await self.cmd_get_role_members(self.mock_interaction, ROLE.MEMBER)

        call_args = mock_discord_file.call_args
        fp_arg = call_args.kwargs["fp"]
        fp_arg.seek(0)
        content = fp_arg.read().decode("utf-8")
        self.assertEqual(content, "user1, user2, user3")

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_single_member(self, mock_discord_file):
        member1 = self.create_member("onlyuser", [PROSPECT_ROLE_NAME])

        self.mock_interaction.guild.members = [member1]

        await self.cmd_get_role_members(self.mock_interaction, PROSPECT_ROLE_NAME)

        call_args = mock_discord_file.call_args
        fp_arg = call_args.kwargs["fp"]
        fp_arg.seek(0)
        content = fp_arg.read().decode("utf-8")
        self.assertEqual(content, "onlyuser")

        send_args = self.mock_interaction.followup.send.call_args
        self.assertIn("Found **1** members", send_args.args[0])

    async def test_cmd_get_role_members_no_matches(self):
        member1 = self.create_member("user1", [ROLE.MEMBER])
        member2 = self.create_member("user2", [ROLE.MEMBER])

        self.mock_interaction.guild.members = [member1, member2]

        await self.cmd_get_role_members(self.mock_interaction, PROSPECT_ROLE_NAME)

        self.mock_interaction.followup.send.assert_called_once_with(
            "No members with role '**Prospect**' found."
        )

    async def test_cmd_get_role_members_empty_guild(self):
        self.mock_interaction.guild.members = []

        await self.cmd_get_role_members(self.mock_interaction, ROLE.MEMBER)

        self.mock_interaction.followup.send.assert_called_once_with(
            "No members with role '**Member**' found."
        )

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_case_sensitive_role_matching(
        self, mock_discord_file
    ):
        member1 = self.create_member("user1", ["Member"])
        member2 = self.create_member("user2", ["MEMBER"])
        member3 = self.create_member("user3", ["member"])

        self.mock_interaction.guild.members = [member1, member2, member3]

        await self.cmd_get_role_members(self.mock_interaction, "member")

        call_args = mock_discord_file.call_args
        fp_arg = call_args.kwargs["fp"]
        fp_arg.seek(0)
        content = fp_arg.read().decode("utf-8")
        self.assertEqual(content, "user3")

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_multiple_roles_per_member(
        self, mock_discord_file
    ):
        member1 = self.create_member("user1", [ROLE.MEMBER, PROSPECT_ROLE_NAME])
        member2 = self.create_member("user2", [PROSPECT_ROLE_NAME, ROLE.STAFF])
        member3 = self.create_member("user3", [ROLE.STAFF])

        self.mock_interaction.guild.members = [member1, member2, member3]

        await self.cmd_get_role_members(self.mock_interaction, PROSPECT_ROLE_NAME)

        call_args = mock_discord_file.call_args
        fp_arg = call_args.kwargs["fp"]
        fp_arg.seek(0)
        content = fp_arg.read().decode("utf-8")
        self.assertEqual(content, "user1, user2")

    @patch("ironforgedbot.commands.admin.cmd_get_role_members.discord.File")
    async def test_cmd_get_role_members_filename_generation(self, mock_discord_file):
        member1 = self.create_member("user1", ["Test Role With Spaces"])

        self.mock_interaction.guild.members = [member1]

        await self.cmd_get_role_members(self.mock_interaction, "Test Role With Spaces")

        call_args = mock_discord_file.call_args
        filename = call_args.kwargs["filename"]
        self.assertTrue(filename.startswith("test_role_with_spaces_role_list_"))
        self.assertTrue(filename.endswith(".txt"))

    async def test_cmd_get_role_members_role_case_insensitive_search(self):
        member1 = self.create_member("user1", ["TestRole"])
        member2 = self.create_member("user2", ["testrole"])

        self.mock_interaction.guild.members = [member1, member2]

        await self.cmd_get_role_members(self.mock_interaction, "TESTROLE")

        self.mock_interaction.followup.send.assert_called_once_with(
            "No members with role '**TESTROLE**' found."
        )
