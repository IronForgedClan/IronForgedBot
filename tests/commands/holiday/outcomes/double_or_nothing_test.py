"""Tests for the double-or-nothing outcome in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.holiday.outcomes import double_or_nothing
from ironforgedbot.commands.holiday.outcomes.double_or_nothing import (
    DoubleOrNothingView,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.state import STATE
from tests.helpers import (
    MOCK_TRICK_OR_TREAT_DATA,
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    setup_database_service_mocks,
)


class TestDoubleOrNothingOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for double-or-nothing outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    @patch("ironforgedbot.commands.holiday.outcomes.double_or_nothing.STATE")
    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_result_double_or_nothing_creates_offer(
        self, mock_member_service_class, mock_db, mock_state
    ):
        """Test that double-or-nothing creates an offer with buttons."""
        mock_state.state = {
            "double_or_nothing_offers": {},
        }

        handler = create_test_trick_or_treat_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1500,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=2000)

        await double_or_nothing.result_double_or_nothing(handler, self.interaction)

        # Verify ingots were added
        handler._adjust_ingots.assert_called_once()

        # Verify a view was sent (has the button)
        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

        # Verify offer was stored in state
        user_id_str = str(self.test_user.id)
        self.assertIn(user_id_str, mock_state.state["double_or_nothing_offers"])

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_process_double_or_nothing_win(
        self, mock_member_service_class, mock_db
    ):
        """Test processing a winning double-or-nothing gamble."""
        handler = create_test_trick_or_treat_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2500,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=3000)

        # Mock random to always win
        with patch("ironforgedbot.commands.holiday.outcomes.double_or_nothing.random.random", return_value=0.3):
            await double_or_nothing.process_double_or_nothing(handler, self.interaction, 500)

        # Should add the amount (winning)
        handler._adjust_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_process_double_or_nothing_lose(
        self, mock_member_service_class, mock_db
    ):
        """Test processing a losing double-or-nothing gamble."""
        handler = create_test_trick_or_treat_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=500)

        # Mock random to always lose
        with patch("ironforgedbot.commands.holiday.outcomes.double_or_nothing.random.random", return_value=0.7):
            await double_or_nothing.process_double_or_nothing(handler, self.interaction, 500)

        # Should remove the amount (losing)
        handler._adjust_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_double_or_nothing_keep_callback(
        self, mock_member_service_class, mock_db
    ):
        """Test that keep winnings button works correctly."""
        handler = create_test_trick_or_treat_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        view = DoubleOrNothingView(handler, self.test_user.id, 500)
        view.message = AsyncMock()

        # Simulate keep button click
        await view._keep_callback(self.interaction)

        # Should defer and delete message
        self.interaction.response.defer.assert_called_once()
        view.message.delete.assert_called_once()

        # Should send keep message
        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("kept", embed.description.lower())

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_double_or_nothing_timeout(
        self, mock_member_service_class, mock_db
    ):
        """Test that double-or-nothing view times out correctly."""
        handler = create_test_trick_or_treat_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        view = DoubleOrNothingView(handler, self.test_user.id, 500)
        view.message = AsyncMock()

        # Simulate timeout
        await view.on_timeout()

        # Should clear items and edit message
        self.assertEqual(len(view.children), 0)
        view.message.edit.assert_called_once()
        embed = view.message.edit.call_args.kwargs["embed"]
        self.assertIn("expired", embed.description.lower())
