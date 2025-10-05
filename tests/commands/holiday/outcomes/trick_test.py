"""Tests for the trick outcome in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.holiday.outcomes import trick
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.commands.holiday.test_helpers import (
    create_test_handler,
    create_test_interaction,
)
from tests.helpers import (
    create_test_db_member,
    create_test_member,
    setup_database_service_mocks,
)


class TestTrickOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for trick outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_test_interaction(user=self.test_user)

    @patch("ironforgedbot.commands.holiday.outcomes.trick.db")
    @patch("ironforgedbot.commands.holiday.outcomes.trick.MemberService")
    async def test_trick_remove_all_with_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test trick outcome when user has ingots (displays fake removal)."""
        handler = create_test_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=5000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        await trick.result_remove_all_ingots_trick(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        # Should show the fake removal message
        self.assertIn("5", embed.description)

    @patch("ironforgedbot.commands.holiday.outcomes.trick.db")
    @patch("ironforgedbot.commands.holiday.outcomes.trick.MemberService")
    async def test_trick_remove_all_no_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test trick outcome when user has no ingots."""
        handler = create_test_handler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=0,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        await trick.result_remove_all_ingots_trick(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        # Should show no ingots message
        self.assertIn("no ingots", embed.description.lower())
