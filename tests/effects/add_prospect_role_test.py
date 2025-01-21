from datetime import datetime
import unittest
from unittest.mock import AsyncMock, Mock, call, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.effects.add_prospect_role import add_prospect_role
from ironforgedbot.storage.types import Member, StorageError
from tests.helpers import create_test_member


class TestAddProspectRoleEffect(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.effects.add_prospect_role.datetime")
    @patch("ironforgedbot.effects.add_prospect_role.STORAGE", new_callable=AsyncMock)
    async def test_timestamp_is_saved(self, mock_storage, mock_datetime):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        expected_datetime = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = expected_datetime

        mock_storage.read_member.return_value = Member(
            id=member.id,
            runescape_name=member.display_name,
            joined_date="unknown",
        )

        await add_prospect_role(mock_report_channel, member)

        mock_storage.update_members.assert_called_with(
            [
                Member(
                    id=member.id,
                    runescape_name=member.display_name,
                    ingots=0,
                    joined_date=expected_datetime.isoformat(),
                )
            ],
            "BOT",
            "Added Prospect role",
        )

    @patch("ironforgedbot.effects.add_prospect_role.datetime")
    @patch("ironforgedbot.effects.add_prospect_role.STORAGE", new_callable=AsyncMock)
    async def test_should_report_when_called(self, mock_storage, mock_datetime):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        expected_datetime = datetime.fromisoformat("2024-01-01T12:00:00Z")
        mock_datetime.now.return_value = expected_datetime

        mock_storage.read_member.return_value = Member(
            id=member.id,
            runescape_name=member.display_name,
            joined_date="unknown",
        )

        await add_prospect_role(mock_report_channel, member)

        calls = [
            str(call_args) for call_args in mock_report_channel.send.call_args_list
        ]
        self.assertEqual(len(calls), 2)

        expected_calls = [
            str(
                call(
                    f":information: {member.mention} has been given the "
                    f"{text_bold(ROLE.PROSPECT)} role, saving timestamp...",
                )
            ),
            str(
                call(
                    f":information: Timestamp for {member.mention} "
                    f"saved: <t:{int(expected_datetime.timestamp())}:d>",
                )
            ),
        ]

        self.assertEqual(calls, expected_calls)

    @patch("ironforgedbot.effects.add_prospect_role.STORAGE", new_callable=AsyncMock)
    async def test_should_report_when_failed_to_get_storage_member(self, mock_storage):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        mock_storage.read_member.side_effect = StorageError("error")

        await add_prospect_role(mock_report_channel, member)

        mock_report_channel.send.assert_called_with(
            f":warning: {text_bold('WARNING')}\nAdded the "
            f"{text_bold(ROLE.PROSPECT)} role to a member that doesn't exist in "
            f"storage. Timestamp can therefore not be saved.\n\n"
            f"Please make sure the member {member.mention} has the "
            f"{text_bold(ROLE.MEMBER)} role and has been successfully synchonized. "
            f"Then add the {text_bold(ROLE.PROSPECT)} role again to successfully "
            "save a timestamp. Adding both roles at once is only supported on mobile."
        )

        mock_storage.update_members.assert_not_called()
