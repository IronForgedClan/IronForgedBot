from datetime import datetime
import unittest
from unittest.mock import AsyncMock, Mock, call, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.storage.types import Member
from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks
from tests.helpers import create_mock_discord_guild, create_test_member


class RefreshRanksTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks(self, mock_sleep, mock_get_points):
        """Happy path with no additional reports"""
        mock_guild = create_mock_discord_guild(
            [create_test_member("foo", [ROLE.MEMBER, RANK.IRON], "bar")]
        )
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.return_value = 100

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_ignore_specific_roles(self, mock_sleep):
        """Should ignore specific roles"""
        mock_guild = create_mock_discord_guild(
            [
                create_test_member("foo", [ROLE.APPLICANT], "applicant"),
                create_test_member("foo", [ROLE.GUEST], "guest"),
            ]
        )
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call("Finished rank check: [2/2]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_notifies_no_nickname(self, mock_sleep):
        """Reporting of members without nicknames set"""
        member = create_test_member("foo", [ROLE.MEMBER], "")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call(f"{member.mention} has no nickname set, ignoring..."),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_ignore_god_alignment_roles(self, mock_sleep):
        """Should ignore God ranks with alignment set"""
        member = create_test_member(
            "foo", [ROLE.MEMBER, RANK.GOD, GOD_ALIGNMENT.GUTHIX], "bar"
        )
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_report_god_role_no_alignment(self, mock_sleep):
        """Should report users with God role but no alignment"""
        member = create_test_member("foo", [ROLE.MEMBER, RANK.GOD], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)

        mock_sleep.return_value = None

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call(f"{member.mention} has  God rank but no alignment."),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_report_no_valid_role(
        self, mock_sleep, mock_get_points
    ):
        """Should report users with no valid role set"""
        member = create_test_member("foo", [], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.return_value = 705

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call(
                f"{member.mention} detected without any rank. Should have  **Mithril**."
            ),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_lookup_failure_results_in_iron_rank(
        self, mock_sleep, mock_get_points
    ):
        """When unable to look up members score, assume score of 0"""
        member = create_test_member("foo", [ROLE.PROSPECT, ROLE.MEMBER], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.side_effect = Exception()

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call(f"Error calculating points for {member.mention}."),
            call("Finished rank check: [1/1]"),
        ]
        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_member_need_upgrading(
        self, mock_sleep, mock_get_points
    ):
        """Reports when member needs upgrading a rank"""
        actual_points = 705
        member = create_test_member("foo", [ROLE.MEMBER, RANK.IRON], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.return_value = actual_points

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call(
                f"{member.mention} needs upgrading  "
                f"→  ({text_bold(f"{actual_points:,}")} points)"
            ),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.job_refresh_ranks.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_report_completed_prospects(
        self, mock_sleep, mock_get_points, mock_storage
    ):
        """Reports when member has completed their probation period"""
        actual_points = 705
        member = create_test_member("foo", [ROLE.PROSPECT], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.return_value = actual_points
        mock_storage.read_member.return_value = Member(
            id=member.id,
            runescape_name=member.display_name,
            joined_date=datetime.fromisoformat("2020-01-01T10:10:10.000000+00:00"),
        )

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call(
                f"{member.mention} has completed their **14 day** probation period and "
                f"is now eligible for  **Mithril** rank."
            ),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.job_refresh_ranks.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_ignore_prospect_during_probation(
        self, mock_sleep, mock_get_points, mock_storage
    ):
        """Ignores when member has not yet completed their probation period"""
        actual_points = 705
        member = create_test_member("foo", [ROLE.PROSPECT], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.return_value = actual_points
        mock_storage.read_member.return_value = Member(
            id=member.id,
            runescape_name=member.display_name,
            joined_date=datetime.fromisoformat("2120-01-01T10:10:10.000000+00:00"),
        )

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Starting rank check..."),
            call("Finished rank check: [1/1]"),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)
