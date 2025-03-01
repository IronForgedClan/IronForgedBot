import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.effects.nickname_change import nickname_change
from tests.helpers import create_test_member


class TestNicknameChangeEffect(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.effects.nickname_change.job_sync_members")
    async def test_job_is_called(self, mock_sync_members):
        before = create_test_member("tester1", [ROLE.MEMBER], "tester1")
        after = create_test_member("tester2", [ROLE.MEMBER], "tester2")
        mock_report_channel = Mock(discord.TextChannel)

        await nickname_change(mock_report_channel, before, after)

        mock_sync_members.assert_called_once_with(
            mock_report_channel.guild, mock_report_channel
        )

    @patch("ironforgedbot.effects.nickname_change.job_sync_members")
    async def test_report_when_called(self, mock_sync_members):
        before = create_test_member("tester1", [ROLE.MEMBER], "tester1")
        after = create_test_member("tester2", [ROLE.MEMBER], "tester2")
        mock_report_channel = Mock(discord.TextChannel)

        await nickname_change(mock_report_channel, before, after)

        mock_report_channel.send.assert_called_once_with(
            f":information: Name change detected: {text_bold(before.display_name)} → "
            f"{text_bold(after.display_name)}. Initiating member sync..."
        )

    @patch("ironforgedbot.effects.nickname_change.job_sync_members")
    async def test_should_ignore_if_not_member(self, mock_sync_members):
        before = create_test_member("tester1", [ROLE.APPLICANT], "tester1")
        after = create_test_member("tester2", [ROLE.APPLICANT], "tester2")
        mock_report_channel = Mock(discord.TextChannel)

        await nickname_change(mock_report_channel, before, after)

        mock_report_channel.send.assert_not_called()
