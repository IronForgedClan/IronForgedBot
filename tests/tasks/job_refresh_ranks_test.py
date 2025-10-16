from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.services.score_service import HiscoresNotFound
from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks
from tests.helpers import (
    create_mock_discord_guild,
    create_test_member,
    create_test_db_member,
    setup_database_service_mocks,
    setup_time_mocks,
)


class TestJobRefreshRanks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()

        self.mock_member = Mock(spec=discord.Member)
        self.mock_member.id = 12345
        self.mock_member.mention = "<@12345>"

        self.mock_db_member = create_test_db_member(
            nickname="TestPlayer",
            discord_id=12345,
            joined_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    async def test_job_refresh_ranks_success(
        self,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests successful rank refresh with valid member data and score tracking."""

        mock_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_create_member_service
        )
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 150
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = create_test_member("TestUser", [RANK.IRON])
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        mock_member_service.get_all_active_members.assert_called_once()
        mock_history_service.track_score.assert_called_once_with(12345, 150)
        mock_member_service.close.assert_called_once()

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    async def test_job_refresh_ranks_member_not_found(
        self,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that a report is sent when an active member is not found in the guild."""

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        self.mock_guild.get_member.return_value = None

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        # Check that the message content appears in one of the sent messages
        expected_text = f"- {self.mock_db_member.nickname} (ID: {self.mock_db_member.id}) not found in guild"
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected text '{expected_text}' not found in any sent message",
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    async def test_job_refresh_ranks_banned_member_skipped(
        self,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that banned members are skipped during rank refresh."""

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_discord_member = create_test_member("TestUser", [ROLE.MEMBER])
        mock_is_banned.return_value = True
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        mock_history_service.track_score.assert_not_called()

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_member")
    async def test_job_refresh_ranks_god_alignment_skipped(
        self,
        mock_get_rank,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that members with God alignment are skipped but their scores are still tracked."""

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 150
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = Mock(spec=discord.Member)
        mock_is_banned.return_value = False
        mock_get_rank.return_value = GOD_ALIGNMENT.GUTHIX
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        mock_history_service.track_score.assert_called_once_with(12345, 150)

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_member")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    async def test_job_refresh_ranks_god_no_alignment_reported(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that members with God rank but no alignment are reported."""
        mock_find_emoji.return_value = "👑"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 150
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_discord_member.roles = []
        mock_is_banned.return_value = False
        mock_get_rank.return_value = RANK.GOD
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        # Check that the message content appears in one of the sent messages
        expected_text = "- <@12345> has 👑 God rank - missing alignment"
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected text '{expected_text}' not found in any sent message",
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_member")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    @patch("ironforgedbot.tasks.job_refresh_ranks.text_bold")
    async def test_job_refresh_ranks_no_rank_reported(
        self,
        mock_text_bold,
        mock_find_emoji,
        mock_get_rank_from_points,
        mock_get_rank,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that members without any rank are reported with the rank they should have."""
        mock_find_emoji.return_value = "🥉"
        mock_text_bold.side_effect = lambda x: f"**{x}**"
        mock_get_rank_from_points.return_value = RANK.MITHRIL

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 705
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_discord_member.roles = []
        mock_is_banned.return_value = False
        mock_get_rank.return_value = None
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        # Check that the message content appears in one of the sent messages
        expected_text = (
            "- <@12345> missing rank → should be 🥉 **Mithril** (**705** points)"
        )
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected text '{expected_text}' not found in any sent message",
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_member")
    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    async def test_job_refresh_ranks_hiscores_not_found_reported(
        self,
        mock_check_role,
        mock_get_rank,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that members not found on hiscores are reported for suspected name change or ban."""

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.side_effect = HiscoresNotFound()
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_discord_member.roles = []
        mock_is_banned.return_value = False
        mock_get_rank.return_value = RANK.DRAGON
        mock_check_role.return_value = False
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        # Check that the message content appears in one of the sent messages
        expected_text = (
            "- <@12345> not found on hiscores - likely RSN change or OSRS ban"
        )
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected text '{expected_text}' not found in any sent message",
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_member")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    @patch("ironforgedbot.tasks.job_refresh_ranks.text_bold")
    async def test_job_refresh_ranks_member_needs_upgrading(
        self,
        mock_text_bold,
        mock_find_emoji,
        mock_check_role,
        mock_get_rank_from_points,
        mock_get_rank,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that members whose points qualify for a higher rank are reported for upgrade."""
        mock_find_emoji.side_effect = lambda target: (
            "⚪" if target == RANK.IRON else "🥉"
        )
        mock_text_bold.side_effect = lambda x: f"**{x}**"
        mock_get_rank_from_points.return_value = RANK.MITHRIL

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 705
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_discord_member.roles = []
        mock_is_banned.return_value = False
        mock_get_rank.return_value = RANK.IRON
        mock_check_role.return_value = False
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        # Check that the message content appears in one of the sent messages
        expected_text = "- <@12345> upgrade ⚪ → 🥉 (**705** points)"
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected text '{expected_text}' not found in any sent message",
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_member")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    @patch("ironforgedbot.tasks.job_refresh_ranks.text_bold")
    async def test_job_refresh_ranks_member_flagged_for_downgrade(
        self,
        mock_text_bold,
        mock_find_emoji,
        mock_check_role,
        mock_get_rank_from_points,
        mock_get_rank,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Tests that members whose points no longer qualify for current rank are flagged for downgrade."""
        mock_find_emoji.side_effect = lambda target: (
            "🐉" if target == RANK.DRAGON else "🟢"
        )
        mock_text_bold.side_effect = lambda x: f"**{x}**"
        mock_get_rank_from_points.return_value = RANK.ADAMANT

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 1000
        mock_get_score_service.return_value = mock_score_service

        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_discord_member.roles = []
        mock_is_banned.return_value = False
        mock_get_rank.return_value = RANK.DRAGON
        mock_check_role.return_value = False
        self.mock_guild.get_member.return_value = mock_discord_member

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        # Check that the message content appears in one of the sent messages
        expected_text = (
            "- <@12345> downgrade 🐉 → 🟢 (**1,000** points) (Verify before changing)"
        )
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected text '{expected_text}' not found in any sent message",
        )
