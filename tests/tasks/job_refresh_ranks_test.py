import unittest
from unittest.mock import AsyncMock, Mock, call, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
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
            call("Beginning rank check..."),
            call("Finished rank check."),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_ignore_specific_roles(self, mock_sleep):
        """Should ignore specific roles"""
        mock_guild = create_mock_discord_guild(
            [
                create_test_member("foo", [ROLE.PROSPECT], "prospect"),
                create_test_member("foo", [ROLE.APPLICANT], "applicant"),
                create_test_member("foo", [ROLE.GUEST], "guest"),
            ]
        )
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Beginning rank check..."),
            call("Finished rank check."),
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
            call("Beginning rank check..."),
            call(
                f"{member.mention} is not a Prospect, Applicant, Guest or Bot "
                "and has no nickname set, ignoring..."
            ),
            call("Finished rank check."),
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
            call("Beginning rank check..."),
            call("Finished rank check."),
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
            call("Beginning rank check..."),
            call(f"{member.mention} has God role but no alignment."),
            call("Finished rank check."),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_report_no_valid_role(self, mock_sleep):
        """Should report users with no valid role set"""
        member = create_test_member("foo", [], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Beginning rank check..."),
            call(f"{member.mention} detected without any ranked role, ignoring..."),
            call("Finished rank check."),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_player_points_total")
    @patch(
        "ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep", new_callable=AsyncMock
    )
    async def test_job_refresh_ranks_report_unable_to_lookup_score(
        self, mock_sleep, mock_get_points
    ):
        """Reports when unable to look up members score"""
        member = create_test_member("foo", [ROLE.MEMBER, RANK.IRON], "bar")
        mock_guild = create_mock_discord_guild([member])
        mock_report_channel = Mock(discord.TextChannel)
        mock_sleep.return_value = None
        mock_get_points.side_effect = Exception()

        await job_refresh_ranks(mock_guild, mock_report_channel)

        expected_messages = [
            call("Beginning rank check..."),
            call(
                f"Error calculating points for {member.mention}. Is their nickname correct?"
            ),
            call("Finished rank check."),
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
            call("Beginning rank check..."),
            call(
                f"{member.mention} needs upgrading  "
                f"→  ({text_bold(f"{actual_points:,}")} points)"
            ),
            call("Finished rank check."),
        ]

        self.assertEqual(mock_report_channel.send.call_args_list, expected_messages)
