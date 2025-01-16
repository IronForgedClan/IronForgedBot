import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.effects.remove_member_role import remove_member_role
from tests.helpers import create_test_member


class TestRemoveMemberRoleEffect(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.effects.remove_member_role.job_sync_members")
    async def test_job_is_called(self, mock_sync_members):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        await remove_member_role(mock_report_channel, member)

        mock_sync_members.assert_called_once_with(
            mock_report_channel.guild, mock_report_channel
        )

    @patch("ironforgedbot.effects.remove_member_role.job_sync_members")
    async def test_report_when_called(self, mock_sync_members):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        await remove_member_role(mock_report_channel, member)

        mock_report_channel.send.assert_called_once_with(
            f":information: {member.mention} has been stripped of the "
            f"{text_bold(ROLE.MEMBER)} role. Initiating member sync..."
        )
