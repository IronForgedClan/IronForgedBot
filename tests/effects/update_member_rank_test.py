import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.effects.update_member_rank import update_member_rank
from tests.helpers import create_test_member


class UpdateMemberRankTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.member = create_test_member(
            "TestUser", [ROLE.MEMBER, RANK.IRON], "TestUser"
        )
        self.member.id = 123456789
        self.member.display_name = "TestUser"
        self.member.mention = "<@123456789>"

    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    async def test_ignores_non_member_role_changes(self, mock_check_role):
        mock_check_role.return_value = False

        await update_member_rank(self.mock_report_channel, self.member)

        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.effects.update_member_rank.find_emoji")
    @patch("ironforgedbot.effects.update_member_rank.get_rank_from_member")
    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    @patch("ironforgedbot.effects.update_member_rank.db")
    async def test_updates_rank_successfully(
        self, mock_db, mock_check_role, mock_get_rank, mock_emoji
    ):
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.MITHRIL
        mock_emoji.return_value = "🗡️"
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.id = 1
        mock_member.rank = RANK.IRON
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_rank = AsyncMock()

        with patch(
            "ironforgedbot.effects.update_member_rank.MemberService",
            return_value=mock_service,
        ):
            await update_member_rank(self.mock_report_channel, self.member)

        mock_service.change_rank.assert_called_once_with(1, RANK.MITHRIL)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("Rank changed", call_args)
        self.assertIn("Mithril", call_args)

    @patch("ironforgedbot.effects.update_member_rank.get_rank_from_member")
    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    async def test_handles_rank_not_determined(self, mock_check_role, mock_get_rank):
        mock_check_role.return_value = True
        mock_get_rank.return_value = None

        await update_member_rank(self.mock_report_channel, self.member)

        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("rank could not be determined", call_args)

    @patch("ironforgedbot.effects.update_member_rank.get_rank_from_member")
    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    @patch("ironforgedbot.effects.update_member_rank.db")
    async def test_handles_member_not_found_in_database(
        self, mock_db, mock_check_role, mock_get_rank
    ):
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.MITHRIL
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        with patch(
            "ironforgedbot.effects.update_member_rank.MemberService",
            return_value=mock_service,
        ):
            await update_member_rank(self.mock_report_channel, self.member)

        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("database member not found", call_args)
        self.assertIn("Mithril", call_args)

    @patch("ironforgedbot.effects.update_member_rank.get_rank_from_member")
    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    @patch("ironforgedbot.effects.update_member_rank.db")
    async def test_ignores_when_rank_unchanged(
        self, mock_db, mock_check_role, mock_get_rank
    ):
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.rank = RANK.IRON
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)

        with patch(
            "ironforgedbot.effects.update_member_rank.MemberService",
            return_value=mock_service,
        ):
            await update_member_rank(self.mock_report_channel, self.member)

        mock_service.change_rank.assert_not_called()
        self.mock_report_channel.send.assert_not_called()

    @patch("ironforgedbot.effects.update_member_rank.find_emoji")
    @patch("ironforgedbot.effects.update_member_rank.GOD_ALIGNMENT")
    @patch("ironforgedbot.effects.update_member_rank.get_rank_from_member")
    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    @patch("ironforgedbot.effects.update_member_rank.db")
    async def test_converts_god_alignment_ranks_to_god(
        self, mock_db, mock_check_role, mock_get_rank, mock_god_alignment, mock_emoji
    ):
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.GOD_SARADOMIN
        mock_god_alignment.list.return_value = [
            RANK.GOD_SARADOMIN,
            RANK.GOD_ZAMORAK,
            RANK.GOD_GUTHIX,
        ]
        mock_emoji.return_value = "👑"
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.id = 1
        mock_member.rank = RANK.IRON
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_rank = AsyncMock()

        with patch(
            "ironforgedbot.effects.update_member_rank.MemberService",
            return_value=mock_service,
        ):
            await update_member_rank(self.mock_report_channel, self.member)

        mock_service.change_rank.assert_called_once_with(1, RANK.GOD)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("God", call_args)

    @patch("ironforgedbot.effects.update_member_rank.find_emoji")
    @patch("ironforgedbot.effects.update_member_rank.get_rank_from_member")
    @patch("ironforgedbot.effects.update_member_rank.check_member_has_role")
    @patch("ironforgedbot.effects.update_member_rank.db")
    async def test_rank_update_with_emoji_display(
        self, mock_db, mock_check_role, mock_get_rank, mock_emoji
    ):
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.ADAMANT
        mock_emoji.return_value = "💎"
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_member = Mock()
        mock_member.id = 1
        mock_member.rank = RANK.MITHRIL
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)
        mock_service.change_rank = AsyncMock()

        with patch(
            "ironforgedbot.effects.update_member_rank.MemberService",
            return_value=mock_service,
        ):
            await update_member_rank(self.mock_report_channel, self.member)

        mock_emoji.assert_called_once_with(RANK.ADAMANT)
        mock_service.change_rank.assert_called_once_with(1, RANK.ADAMANT)
        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("💎", call_args)
        self.assertIn("Adamant", call_args)
