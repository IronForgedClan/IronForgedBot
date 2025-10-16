from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.services.score_service import HiscoresNotFound
from ironforgedbot.tasks.job_refresh_ranks import (
    build_missing_member_message,
    build_hiscores_not_found_message,
    build_fetch_error_message,
    build_god_no_alignment_message,
    build_invalid_join_date_message,
    build_probation_completed_message,
    build_missing_rank_message,
    build_rank_upgrade_message,
    build_rank_downgrade_message,
    fetch_member_points,
    process_member_rank_check,
    job_refresh_ranks,
)
from tests.helpers import (
    create_test_member,
    create_test_db_member,
)


class TestMessageBuilders(unittest.TestCase):
    """Unit tests for message builder functions."""

    def test_build_missing_member_message(self):
        result = build_missing_member_message("TestPlayer", 12345)
        self.assertEqual(result, "- TestPlayer (ID: 12345) not found in guild")

    def test_build_hiscores_not_found_message(self):
        result = build_hiscores_not_found_message("<@12345>")
        self.assertEqual(
            result, "- <@12345> not found on hiscores - likely RSN change or ban"
        )

    def test_build_fetch_error_message(self):
        result = build_fetch_error_message("<@12345>")
        self.assertEqual(result, "- Failed to fetch points for <@12345> - check logs")

    def test_build_god_no_alignment_message(self):
        result = build_god_no_alignment_message("<@12345>", "👑")
        self.assertEqual(result, "- <@12345> has 👑 God rank but missing alignment")

    def test_build_invalid_join_date_message(self):
        result = build_invalid_join_date_message("<@12345>", "Prospect")
        self.assertIn("<@12345>", result)
        self.assertIn("Prospect", result)
        self.assertIn("invalid join date", result)

    def test_build_probation_completed_message(self):
        result = build_probation_completed_message("<@12345>", "⚪", "Iron")
        self.assertIn("<@12345>", result)
        self.assertIn("⚪", result)
        self.assertIn("Iron", result)
        self.assertIn("eligible", result)

    def test_build_missing_rank_message(self):
        result = build_missing_rank_message("<@12345>", "🥉", "Mithril", 705)
        self.assertIn("<@12345>", result)
        self.assertIn("🥉", result)
        self.assertIn("Mithril", result)
        self.assertIn("705", result)
        self.assertIn("missing rank", result)

    def test_build_rank_upgrade_message(self):
        result = build_rank_upgrade_message("<@12345>", "⚪", "🥉", 705)
        self.assertIn("<@12345>", result)
        self.assertIn("⚪", result)
        self.assertIn("🥉", result)
        self.assertIn("705", result)
        self.assertIn("upgrade", result)

    def test_build_rank_downgrade_message(self):
        result = build_rank_downgrade_message("<@12345>", "🐉", "🟢", 1000)
        self.assertIn("<@12345>", result)
        self.assertIn("🐉", result)
        self.assertIn("🟢", result)
        self.assertIn("1,000", result)
        self.assertIn("downgrade", result)
        self.assertIn("Verify before changing", result)


class TestFetchMemberPoints(unittest.IsolatedAsyncioTestCase):
    """Unit tests for fetch_member_points helper function."""

    async def test_success_returns_points(self):
        """Test successful points fetch returns points and no error."""
        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.return_value = 705

        points, error = await fetch_member_points(
            "TestPlayer", mock_discord_member, RANK.IRON, mock_score_service
        )

        self.assertEqual(points, 705)
        self.assertIsNone(error)
        mock_score_service.get_player_points_total.assert_called_once_with(
            "TestPlayer", bypass_cache=True
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    async def test_hiscores_not_found_for_ranked_member_returns_error(
        self, mock_check_role
    ):
        """Test HiscoresNotFound for ranked members returns error message."""
        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_check_role.return_value = False

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.side_effect = HiscoresNotFound()

        points, error = await fetch_member_points(
            "TestPlayer", mock_discord_member, RANK.DRAGON, mock_score_service
        )

        self.assertEqual(points, 0)
        self.assertIsNotNone(error)
        self.assertIn("<@12345>", error)
        self.assertIn("not found on hiscores", error)

    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    async def test_hiscores_not_found_for_prospect_returns_no_error(
        self, mock_check_role
    ):
        """Test HiscoresNotFound for prospects returns no error (silently skipped)."""
        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"
        mock_check_role.return_value = True

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.side_effect = HiscoresNotFound()

        points, error = await fetch_member_points(
            "TestPlayer", mock_discord_member, RANK.IRON, mock_score_service
        )

        self.assertEqual(points, 0)
        self.assertIsNone(error)

    async def test_generic_exception_returns_error(self):
        """Test generic exceptions return error message."""
        mock_discord_member = Mock(spec=discord.Member)
        mock_discord_member.mention = "<@12345>"

        mock_score_service = AsyncMock()
        mock_score_service.get_player_points_total.side_effect = Exception("API Error")

        points, error = await fetch_member_points(
            "TestPlayer", mock_discord_member, RANK.IRON, mock_score_service
        )

        self.assertEqual(points, 0)
        self.assertIsNotNone(error)
        self.assertIn("<@12345>", error)
        self.assertIn("Failed to fetch points", error)


class TestProcessMemberRankCheck(unittest.TestCase):
    """Unit tests for process_member_rank_check helper function."""

    def setUp(self):
        self.mock_discord_member = Mock(spec=discord.Member)
        self.mock_discord_member.mention = "<@12345>"
        self.mock_discord_member.roles = []

        self.mock_db_member = create_test_db_member(
            nickname="TestPlayer",
            discord_id=12345,
            joined_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    def test_god_alignment_returns_none(self, mock_find_emoji):
        """Test members with God alignment are skipped."""
        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member,
            self.mock_discord_member,
            GOD_ALIGNMENT.GUTHIX,
            1000,
        )

        self.assertIsNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNone(issue)

    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    def test_god_rank_without_alignment_returns_issue(self, mock_find_emoji):
        """Test God rank without alignment returns issue message."""
        mock_find_emoji.return_value = "👑"

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.GOD, 10000
        )

        self.assertIsNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNotNone(issue)
        self.assertIn("👑", issue)
        self.assertIn("God rank but missing alignment", issue)

    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    def test_prospect_with_invalid_join_date_returns_issue(self, mock_check_role):
        """Test prospect with invalid join date returns issue message."""
        mock_check_role.return_value = True
        self.mock_db_member.joined_date = None

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.IRON, 100
        )

        self.assertIsNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNotNone(issue)
        self.assertIn("invalid join date", issue)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    def test_prospect_completed_probation_returns_probation_message(
        self, mock_check_role, mock_find_emoji, mock_get_rank_from_points
    ):
        """Test prospect who completed probation returns probation message."""
        mock_check_role.return_value = True
        mock_find_emoji.return_value = "🥉"
        mock_get_rank_from_points.return_value = RANK.MITHRIL

        old_date = datetime.now(timezone.utc) - timedelta(days=30)
        self.mock_db_member.joined_date = old_date

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.IRON, 705
        )

        self.assertIsNone(rank_change)
        self.assertIsNotNone(probation)
        self.assertIsNone(issue)
        self.assertIn("eligible", probation)
        self.assertIn("🥉", probation)

    @patch("ironforgedbot.tasks.job_refresh_ranks.check_member_has_role")
    def test_prospect_still_on_probation_returns_none(self, mock_check_role):
        """Test prospect still on probation returns all None."""
        mock_check_role.return_value = True
        recent_date = datetime.now(timezone.utc) - timedelta(days=10)
        self.mock_db_member.joined_date = recent_date

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.IRON, 100
        )

        self.assertIsNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNone(issue)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    def test_member_with_no_rank_returns_issue(
        self, mock_find_emoji, mock_get_rank_from_points
    ):
        """Test member without rank returns issue message."""
        mock_find_emoji.return_value = "🥉"
        mock_get_rank_from_points.return_value = RANK.MITHRIL

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, None, 705
        )

        self.assertIsNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNotNone(issue)
        self.assertIn("missing rank", issue)
        self.assertIn("🥉", issue)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    def test_member_needing_upgrade_returns_rank_change(
        self, mock_find_emoji, mock_get_rank_from_points
    ):
        """Test member needing upgrade returns rank change message."""
        mock_find_emoji.side_effect = lambda x: "⚪" if x == RANK.IRON else "🥉"
        mock_get_rank_from_points.return_value = RANK.MITHRIL

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.IRON, 705
        )

        self.assertIsNotNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNone(issue)
        self.assertIn("upgrade", rank_change)
        self.assertIn("⚪", rank_change)
        self.assertIn("🥉", rank_change)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    @patch("ironforgedbot.tasks.job_refresh_ranks.find_emoji")
    def test_member_needing_downgrade_returns_rank_change_with_warning(
        self, mock_find_emoji, mock_get_rank_from_points
    ):
        """Test member needing downgrade returns rank change message with warning."""
        mock_find_emoji.side_effect = lambda x: "🐉" if x == RANK.DRAGON else "🟢"
        mock_get_rank_from_points.return_value = RANK.ADAMANT

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.DRAGON, 1000
        )

        self.assertIsNotNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNone(issue)
        self.assertIn("downgrade", rank_change)
        self.assertIn("🐉", rank_change)
        self.assertIn("🟢", rank_change)
        self.assertIn("Verify before changing", rank_change)

    @patch("ironforgedbot.tasks.job_refresh_ranks.get_rank_from_points")
    def test_member_with_correct_rank_returns_none(self, mock_get_rank_from_points):
        """Test member with correct rank returns all None."""
        mock_get_rank_from_points.return_value = RANK.IRON

        rank_change, probation, issue = process_member_rank_check(
            self.mock_db_member, self.mock_discord_member, RANK.IRON, 100
        )

        self.assertIsNone(rank_change)
        self.assertIsNone(probation)
        self.assertIsNone(issue)


class TestJobRefreshRanks(unittest.IsolatedAsyncioTestCase):
    """Integration tests for job_refresh_ranks orchestration function."""

    def setUp(self):
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()

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
    async def test_job_refresh_ranks_success_tracks_scores(
        self,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Test successful rank refresh fetches points and tracks scores."""
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
    async def test_member_not_found_in_guild_reports_issue(
        self,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Test that members not found in guild are reported as issues."""
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_all_active_members.return_value = [self.mock_db_member]
        mock_create_member_service.return_value = mock_member_service

        mock_history_service = AsyncMock()
        mock_create_score_history_service.return_value = mock_history_service

        self.mock_guild.get_member.return_value = None

        await job_refresh_ranks(self.mock_guild, self.mock_report_channel)

        expected_text = f"- {self.mock_db_member.nickname} (ID: {self.mock_db_member.id}) not found in guild"
        sent_messages = [
            call.args[0] for call in self.mock_report_channel.send.call_args_list
        ]
        self.assertTrue(
            any(expected_text in msg for msg in sent_messages),
            f"Expected issue message not found in sent messages",
        )

    @patch("ironforgedbot.tasks.job_refresh_ranks.asyncio.sleep")
    @patch("ironforgedbot.tasks.job_refresh_ranks.get_score_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_score_history_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.create_member_service")
    @patch("ironforgedbot.tasks.job_refresh_ranks.db")
    @patch("ironforgedbot.tasks.job_refresh_ranks.is_member_banned")
    async def test_banned_member_skipped_no_score_tracking(
        self,
        mock_is_banned,
        mock_db,
        mock_create_member_service,
        mock_create_score_history_service,
        mock_get_score_service,
        mock_sleep,
    ):
        """Test that banned members are skipped without tracking scores."""
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
