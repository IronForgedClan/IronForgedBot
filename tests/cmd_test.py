import unittest
from unittest.mock import Mock, MagicMock

import discord

from ironforgedbot.commands.syncmembers.syncmembers import sync_members
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.main_test import helper_create_member


class TestCommands(unittest.TestCase):
    def test_sync_members(self):
        mock_guild = Mock(discord.Guild)

        member1 = helper_create_member("member1", ROLES.MEMBER, "johnnycache")
        member2 = helper_create_member("member2", ROLES.MEMBER)
        member3 = helper_create_member("member3", ROLES.MEMBER)
        member5 = helper_create_member("member5", ROLES.MEMBER, "")
        mock_guild.members = [member1, member2, member3, member5]

        mock_storage = MagicMock()
        mock_storage.read_members.return_value = [
            Member(id=member1.id, runescape_name="member1", ingots=200),
            # In storage, but nick is not set.
            Member(id=member2.id, runescape_name="Crimson chin", ingots=400),
            Member(id=13, runescape_name="member4", ingots=1000),
        ]

        sync_members(mock_guild, mock_storage)

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
