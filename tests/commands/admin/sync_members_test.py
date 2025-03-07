import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.admin.sync_members import sync_members
from ironforgedbot.common.roles import ROLE
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestSyncMembers(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.admin.sync_members.STORAGE", new_callable=AsyncMock)
    async def test_sync_members(self, mock_storage):
        """Test that sheet can be updated to only members in Discord."""
        caller = create_test_member("leader", [ROLE.LEADERSHIP])
        member1 = create_test_member("member1", [ROLE.MEMBER], "johnnycache")
        member2 = create_test_member("member2", [ROLE.MEMBER])
        member3 = create_test_member("member3", [ROLE.MEMBER], "member3")
        member5 = create_test_member("member5", [ROLE.MEMBER])

        interaction = create_mock_discord_interaction(
            user=caller, members=[member1, member2, member3, member5]
        )

        mock_storage.read_members.return_value = [
            Member(id=member1.id, runescape_name="member1", ingots=200),
            # In storage, but nick is not set.
            Member(id=member2.id, runescape_name="Crimson chin", ingots=400),
            Member(id=13, runescape_name="member4", ingots=1000),
        ]

        assert interaction.guild
        await sync_members(interaction.guild)

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
