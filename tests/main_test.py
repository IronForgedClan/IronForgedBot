import asyncio
import random
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import discord

import main
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member


def helper_create_member(name: str, role: ROLES, nick=None) -> discord.User:
    if nick is None:
        nick = name

    discord_role = Mock(spec=discord.Role)
    discord_role.name = role

    user = Mock(spec=discord.User)
    user.id = random.randint(100, 999)
    user.roles = [role]
    user.name = name
    user.nick = nick
    user.display_name = nick

    return user


class TestIronForgedBot(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        cls.patch_find_emoji = patch("main.find_emoji", return_value="")
        cls.patch_find_emoji.start()

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()
        cls.patch_find_emoji.stop()

    def setUp(self):
        self.mock_interaction = AsyncMock(spec=discord.Interaction)
        self.mock_interaction.followup = AsyncMock()
        self.mock_interaction.is_expired = Mock()
        self.mock_interaction.is_expired.return_value = False
        self.mock_interaction.response = AsyncMock()
        self.mock_interaction.guild = Mock()
        self.mock_interaction.guild.members = []

    @patch("main.validate_protected_request")
    async def test_syncmembers(self, mock_validate_protected_request):
        """Test that sheet can be updated to only members in Discord."""
        caller = helper_create_member("leader", ROLES.LEADERSHIP)

        mock_validate_protected_request.return_value = (
            caller,
            caller.display_name,
        )

        guild = Mock(discord.Guild)

        member1 = helper_create_member("member1", ROLES.MEMBER, "johnnycache")
        member2 = helper_create_member("member2", ROLES.MEMBER)
        member3 = helper_create_member("member3", ROLES.MEMBER)
        member5 = helper_create_member("member5", ROLES.MEMBER, "")
        guild.members = [member1, member2, member3, member5]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        mock_storage = MagicMock()
        mock_storage.read_members.return_value = [
            Member(id=member1.id, runescape_name="member1", ingots=200),
            # In storage, but nick is not set.
            Member(id=member2.id, runescape_name="Crimson chin", ingots=400),
            Member(id=13, runescape_name="member4", ingots=1000),
        ]

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")

        await commands.syncmembers(self.mock_interaction)

        mock_storage.add_members.assert_called_once_with(
            [Member(id=member3.id, runescape_name="member3", ingots=0)],
            "User Joined Server",
        )

        mock_storage.remove_members.assert_called_once_with(
            [Member(id=13, runescape_name="member4", ingots=1000)], "User Left Server"
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(id=member1.id, runescape_name="johnnycache", ingots=200),
                Member(id=member2.id, runescape_name="member2", ingots=400),
            ],
            "Name Change",
        )
