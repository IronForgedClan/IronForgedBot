import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.events.handlers.update_member_rank import UpdateMemberRankHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from tests.helpers import create_test_db_member, create_test_member


class TestUpdateMemberRankHandlerShouldHandle(unittest.TestCase):
    def test_should_handle_true_when_rank_role_added_and_has_member(self):
        """should_handle returns True when rank role added and has Member role."""
        handler = UpdateMemberRankHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER])
        after = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertTrue(handler.should_handle(context))

    def test_should_handle_false_when_rank_role_not_added(self):
        """should_handle returns False when no rank role was added."""
        handler = UpdateMemberRankHandler()

        before = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON])
        after = create_test_member("TestUser", [ROLE.MEMBER, RANK.IRON])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_false_when_no_member_role(self):
        """should_handle returns False when member doesn't have Member role."""
        handler = UpdateMemberRankHandler()

        before = create_test_member("TestUser", [])
        after = create_test_member("TestUser", [RANK.IRON])
        after.id = before.id
        report_channel = Mock(spec=discord.TextChannel)

        context = MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

        self.assertFalse(handler.should_handle(context))

    def test_should_handle_true_for_any_rank(self):
        """should_handle returns True for any rank role addition."""
        handler = UpdateMemberRankHandler()

        for rank in [
            RANK.IRON,
            RANK.MITHRIL,
            RANK.ADAMANT,
            RANK.RUNE,
            RANK.DRAGON,
            RANK.GOD,
        ]:
            before = create_test_member("TestUser", [ROLE.MEMBER])
            after = create_test_member("TestUser", [ROLE.MEMBER, rank])
            after.id = before.id
            report_channel = Mock(spec=discord.TextChannel)

            context = MemberUpdateContext(
                before=before, after=after, report_channel=report_channel
            )

            self.assertTrue(handler.should_handle(context), f"Failed for rank {rank}")


class TestUpdateMemberRankHandlerExecute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = UpdateMemberRankHandler()
        self.mock_session = AsyncMock()
        self.mock_service = AsyncMock()

    def _create_context(self, before_roles=None, after_roles=None):
        before_roles = before_roles or [ROLE.MEMBER]
        after_roles = after_roles or [ROLE.MEMBER, RANK.IRON]

        before = create_test_member("TestUser", before_roles, "TestNick")
        after = create_test_member("TestUser", after_roles, "TestNick")
        after.id = before.id
        after.display_name = "TestNick"

        report_channel = AsyncMock(spec=discord.TextChannel)
        report_channel.send = AsyncMock()
        report_channel.guild = Mock(spec=discord.Guild)

        return MemberUpdateContext(
            before=before, after=after, report_channel=report_channel
        )

    @patch("ironforgedbot.events.handlers.update_member_rank.find_emoji")
    @patch("ironforgedbot.events.handlers.update_member_rank.get_rank_from_member")
    async def test_execute_updates_rank(self, mock_get_rank, mock_emoji):
        """Updates member rank in database when rank changed."""
        mock_get_rank.return_value = RANK.MITHRIL
        mock_emoji.return_value = ""

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id", rank=RANK.IRON
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_rank = AsyncMock()

        context = self._create_context(after_roles=[ROLE.MEMBER, RANK.MITHRIL])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_rank.assert_called_once_with("test-id", RANK.MITHRIL)
        self.assertIn("rank changed", result.lower())

    @patch("ironforgedbot.events.handlers.update_member_rank.get_rank_from_member")
    async def test_execute_no_change_when_rank_same(self, mock_get_rank):
        """Returns None when rank is already the same in database."""
        mock_get_rank.return_value = RANK.IRON

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, rank=RANK.IRON
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.mock_service.change_rank.assert_not_called()
        self.assertIsNone(result)

    @patch("ironforgedbot.events.handlers.update_member_rank.get_rank_from_member")
    async def test_execute_rank_not_determined_returns_warning(self, mock_get_rank):
        """Returns warning when rank cannot be determined."""
        mock_get_rank.return_value = None

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("could not be determined", result.lower())

    @patch("ironforgedbot.events.handlers.update_member_rank.get_rank_from_member")
    async def test_execute_member_not_found_returns_warning(self, mock_get_rank):
        """Returns warning when member not found in database."""
        mock_get_rank.return_value = RANK.IRON
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=None)

        context = self._create_context()

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn("not found", result.lower())

    @patch("ironforgedbot.events.handlers.update_member_rank.find_emoji")
    @patch("ironforgedbot.events.handlers.update_member_rank.get_rank_from_member")
    async def test_execute_god_alignment_maps_to_god(self, mock_get_rank, mock_emoji):
        """God alignment roles are mapped to GOD rank."""
        mock_get_rank.return_value = GOD_ALIGNMENT.ZAMORAK
        mock_emoji.return_value = ""

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id", rank=RANK.IRON
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_rank = AsyncMock()

        context = self._create_context(after_roles=[ROLE.MEMBER, GOD_ALIGNMENT.ZAMORAK])

        await self.handler._execute(context, self.mock_session, self.mock_service)

        self.mock_service.change_rank.assert_called_once_with("test-id", RANK.GOD)

    @patch("ironforgedbot.events.handlers.update_member_rank.find_emoji")
    @patch("ironforgedbot.events.handlers.update_member_rank.get_rank_from_member")
    async def test_execute_shows_previous_and_new_rank(self, mock_get_rank, mock_emoji):
        """Response shows previous and new rank."""
        mock_get_rank.return_value = RANK.ADAMANT
        mock_emoji.return_value = ""

        db_member = create_test_db_member(
            nickname="TestUser", discord_id=12345, id="test-id", rank=RANK.MITHRIL
        )
        self.mock_service.get_member_by_discord_id = AsyncMock(return_value=db_member)
        self.mock_service.change_rank = AsyncMock()

        context = self._create_context(after_roles=[ROLE.MEMBER, RANK.ADAMANT])

        result = await self.handler._execute(
            context, self.mock_session, self.mock_service
        )

        self.assertIn(RANK.MITHRIL, result)
        self.assertIn(str(RANK.ADAMANT), result)


class TestUpdateMemberRankHandlerPriority(unittest.TestCase):
    def test_priority_is_30(self):
        """UpdateMemberRankHandler has priority 30."""
        handler = UpdateMemberRankHandler()
        self.assertEqual(handler.priority, 30)

    def test_name_property(self):
        """Handler name is UpdateMemberRank."""
        handler = UpdateMemberRankHandler()
        self.assertEqual(handler.name, "UpdateMemberRank")
