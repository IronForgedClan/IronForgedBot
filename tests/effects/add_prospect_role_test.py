from datetime import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.effects.add_prospect_role import add_prospect_role
from ironforgedbot.storage.types import Member, StorageError
from tests.helpers import create_mock_discord_guild, create_test_member


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
    async def test_should_report_when_called_and_update(
        self, mock_storage, mock_datetime
    ):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        mock_report_channel = Mock(discord.TextChannel)

        expected_datetime = datetime.fromisoformat("2024-01-01T12:00:00Z")
        mock_datetime.now.return_value = expected_datetime

        mock_storage.read_member.return_value = Member(
            id=member.id,
            runescape_name=member.display_name,
            joined_date="unknown",
        )

        mock_message = MagicMock(spec=discord.Message)
        mock_message.edit = AsyncMock()

        mock_report_channel.send.return_value = mock_message

        await add_prospect_role(mock_report_channel, member)

        mock_report_channel.send.assert_awaited_with(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role, saving timestamp..."
        )
        mock_message.edit.assert_awaited_once_with(
            content=(
                f":information: {member.mention} has been given the "
                f"{text_bold(ROLE.PROSPECT)} role.\n"
                f"Join date saved: <t:{int(expected_datetime.timestamp())}:F>"
            )
        )

    @patch("ironforgedbot.effects.add_prospect_role.STORAGE", new_callable=AsyncMock)
    async def test_should_report_and_fix_when_called_without_member_in_storage(
        self, mock_storage
    ):
        member = create_test_member("tester", [ROLE.PROSPECT], "tester")
        guild = create_mock_discord_guild([member], [ROLE.PROSPECT, ROLE.MEMBER])
        mock_report_channel = Mock(discord.TextChannel)
        mock_report_channel.guild = guild

        mock_storage.read_member.side_effect = StorageError("error")

        await add_prospect_role(mock_report_channel, member)

        mock_report_channel.send.assert_called_with(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role without having the {text_bold(ROLE.MEMBER)} "
            "role. Adding correct roles to member and trying again..."
        )

        member.remove_roles.assert_awaited_once_with(
            guild.roles[0], reason="Prospect role effect"
        )

        member.add_roles.assert_any_await(guild.roles[0], reason="Prospect role effect")
        member.add_roles.assert_any_await(guild.roles[1], reason="Prospect role effect")

        mock_storage.update_members.assert_not_called()
