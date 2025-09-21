import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.effects.add_member_role import _rollback, add_member_role
from ironforgedbot.services.member_service import (
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)
from tests.helpers import (
    create_test_member,
    create_mock_discord_guild,
    setup_database_service_mocks,
    setup_time_mocks,
)


class AddMemberRoleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.mock_guild = create_mock_discord_guild()
        self.mock_report_channel.guild = self.mock_guild
        self.discord_member = create_test_member("TestUser", [ROLE.MEMBER], "TestUser")
        self.discord_member.id = 123456789
        self.discord_member.display_name = "TestUser"
        self.discord_member.mention = "<@123456789>"

    @patch("ironforgedbot.effects.add_member_role.get_discord_role")
    async def test_rollback_removes_member_role(self, mock_get_role):
        mock_member_role = Mock()
        mock_get_role.return_value = mock_member_role
        self.discord_member.remove_roles = AsyncMock()

        await _rollback(self.mock_report_channel, self.discord_member)

        mock_get_role.assert_called_once_with(self.mock_guild, ROLE.MEMBER)
        self.discord_member.remove_roles.assert_called_once_with(
            mock_member_role, reason="Error saving member to database"
        )

    @patch("ironforgedbot.effects.add_member_role.get_discord_role")
    async def test_rollback_raises_error_when_no_role(self, mock_get_role):
        mock_get_role.return_value = None

        with self.assertRaises(ValueError) as context:
            await _rollback(self.mock_report_channel, self.discord_member)

        self.assertEqual(str(context.exception), "Unable to access Member role value")

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_creates_new_member_successfully(
        self, mock_db, mock_get_rank, mock_time
    ):
        setup_time_mocks(None, mock_time, duration_seconds=5.0)
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.id = 1
        mock_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_service.create_member = AsyncMock(return_value=mock_member)

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_service.create_member.assert_called_once_with(
            123456789, "TestUser", RANK.IRON
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("has been given the **Member** role", call_args)
        self.assertIn("new member", call_args)

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role.GOD_ALIGNMENT")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_converts_god_alignment_ranks_to_god(
        self, mock_db, mock_god_alignment, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = RANK.GOD_SARADOMIN
        mock_god_alignment.list.return_value = [
            RANK.GOD_SARADOMIN,
            RANK.GOD_ZAMORAK,
            RANK.GOD_GUTHIX,
        ]
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_service.create_member = AsyncMock(return_value=mock_member)

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_service.create_member.assert_called_once_with(
            123456789, "TestUser", RANK.GOD
        )

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_defaults_to_iron_rank_when_none(
        self, mock_db, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = None
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_service.create_member = AsyncMock(return_value=mock_member)

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_service.create_member.assert_called_once_with(
            123456789, "TestUser", RANK.IRON
        )

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_reactivates_inactive_member_on_discord_id_violation(
        self, mock_db, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_existing_member = Mock()
        mock_existing_member.id = 1
        mock_existing_member.active = False
        mock_existing_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_reactivate_response = Mock()
        mock_reactivate_response.previous_rank = RANK.MITHRIL
        mock_reactivate_response.previous_nick = "OldNick"
        mock_reactivate_response.previous_join_date = datetime(
            2023, 1, 1, tzinfo=timezone.utc
        )
        mock_reactivate_response.approximate_leave_date = datetime(
            2023, 6, 1, tzinfo=timezone.utc
        )
        mock_reactivate_response.previous_ingot_qty = 1500
        mock_reactivate_response.ingots_reset = True
        mock_service.create_member = AsyncMock(side_effect=UniqueDiscordIdVolation())
        mock_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_existing_member
        )
        mock_service.reactivate_member = AsyncMock(
            return_value=mock_reactivate_response
        )

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ), patch(
            "ironforgedbot.effects.add_member_role.find_emoji"
        ) as mock_emoji, patch(
            "ironforgedbot.effects.add_member_role.build_response_embed"
        ) as mock_embed:

            mock_emoji.return_value = "🏆"
            mock_embed_instance = Mock()
            mock_embed.return_value = mock_embed_instance

            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_service.reactivate_member.assert_called_once_with(1, "TestUser", RANK.IRON)
        self.mock_report_channel.send.assert_called_once()

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role._rollback")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_handles_nickname_conflict_on_reactivation(
        self, mock_db, mock_rollback, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_existing_member = Mock()
        mock_existing_member.id = 1
        mock_existing_member.active = False
        mock_conflicting_member = Mock()
        mock_conflicting_member.id = 987654321
        mock_conflicting_member.mention = "<@987654321>"
        mock_conflicting_db_member = Mock()
        mock_conflicting_db_member.id = 2

        mock_service.create_member = AsyncMock(side_effect=UniqueDiscordIdVolation())
        mock_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_existing_member
        )
        mock_service.reactivate_member = AsyncMock(
            side_effect=UniqueNicknameViolation()
        )
        mock_service.get_member_by_nickname = AsyncMock(
            return_value=mock_conflicting_db_member
        )
        self.mock_guild.get_member_named.return_value = mock_conflicting_member

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.discord_member
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("nickname conflict", call_args)
        self.assertIn(mock_conflicting_member.mention, call_args)

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role._rollback")
    @patch("ironforgedbot.effects.add_member_role.logger")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_handles_generic_exception(
        self, mock_db, mock_logger, mock_rollback, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.create_member = AsyncMock(side_effect=Exception("Database error"))

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_logger.error.assert_called_once()
        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.discord_member
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("error occured saving", call_args)

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role._rollback")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_handles_none_member_result(
        self, mock_db, mock_rollback, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.create_member = AsyncMock(return_value=None)

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_rollback.assert_called_once_with(
            self.mock_report_channel, self.discord_member
        )
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("error occured", call_args)

    @patch("ironforgedbot.effects.add_member_role.time")
    @patch("ironforgedbot.effects.add_member_role.get_rank_from_member")
    @patch("ironforgedbot.effects.add_member_role.db")
    async def test_handles_active_member_on_unique_violation(
        self, mock_db, mock_get_rank, mock_time
    ):
        mock_time.perf_counter.side_effect = [0.0, 5.0]
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_existing_member = Mock()
        mock_existing_member.id = 1
        mock_existing_member.active = True
        mock_existing_member.joined_date = datetime(2023, 1, 1, tzinfo=timezone.utc)

        mock_service.create_member = AsyncMock(side_effect=UniqueDiscordIdVolation())
        mock_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_existing_member
        )

        with patch(
            "ironforgedbot.effects.add_member_role.MemberService",
            return_value=mock_service,
        ):
            await add_member_role(self.mock_report_channel, self.discord_member)

        mock_service.reactivate_member.assert_not_called()
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("new member", call_args)
