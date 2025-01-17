from datetime import datetime
import unittest
from unittest.mock import AsyncMock, Mock, patch

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

    @patch("ironforgedbot.effects.add_prospect_role.STORAGE", new_callable=AsyncMock)
    async def test_should_report_when_called(self, mock_storage):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        mock_storage.read_member.return_value = Member(
            id=member.id,
            runescape_name=member.display_name,
            joined_date="unknown",
        )

        await add_prospect_role(mock_report_channel, member)

        mock_report_channel.send.assert_called_once_with(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role, saving timestamp."
        )

    @patch("ironforgedbot.effects.add_prospect_role.STORAGE", new_callable=AsyncMock)
    async def test_should_report_when_failed_to_get_storage_member(self, mock_storage):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        mock_storage.read_member.side_effect = StorageError("error")

        await add_prospect_role(mock_report_channel, member)

        mock_report_channel.send.assert_called_with(
            "An error occured. Please contact the Discord Team."
        )

        mock_storage.update_members.assert_not_called()
