"""Tests for the backrooms outcome in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.commands.trickortreat.outcomes import backrooms
from ironforgedbot.commands.trickortreat.outcomes.backrooms import (
    BackroomsView,
    DoorOutcome,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    setup_database_service_mocks,
)


class TestBackroomsOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for backrooms outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_result_backrooms_creates_view(self):
        """Test that backrooms creates a view with corridor buttons."""
        handler = create_test_trick_or_treat_handler()

        await backrooms.result_backrooms(handler, self.interaction)

        # Verify a view was sent (has the corridor buttons)
        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

        # Verify it's a BackroomsView
        view = call_kwargs["view"]
        self.assertIsInstance(view, BackroomsView)

        # Verify embed was sent
        self.assertIn("embed", call_kwargs)

    async def test_backrooms_view_has_three_doors(self):
        """Test that BackroomsView creates exactly 3 corridor buttons."""
        handler = create_test_trick_or_treat_handler()
        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🟨 Yellow Hallway", "💡 Buzzing Lights", "🚪 Empty Room"]

        view = BackroomsView(handler, self.test_user.id, outcomes, labels)

        # Should have 3 buttons (one for each corridor)
        self.assertEqual(len(view.children), 3)

        # All buttons should be on row 0
        for button in view.children:
            self.assertEqual(button.row, 0)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.MemberService")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_process_door_choice_treasure(
        self, mock_randint, mock_member_service_class, mock_db
    ):
        """Test treasure door outcome."""
        mock_randint.return_value = 3000

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

        # Mock _adjust_ingots to return new total
        handler._adjust_ingots = AsyncMock(return_value=4500)
        # Mock _get_user_info to return nickname and ingots
        handler._get_user_info = AsyncMock(return_value=("TestUser", 1500))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.TREASURE, 0, outcomes, labels
        )

        # Verify ingots were added
        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args
        self.assertEqual(call_args[0][1], 3000)  # Amount added
        self.assertEqual(
            call_args.kwargs["reason"], "Trick or treat: backrooms treasure"
        )

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.MemberService")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_process_door_choice_monster(
        self, mock_randint, mock_member_service_class, mock_db
    ):
        """Test monster door outcome."""
        mock_randint.return_value = 2000

        handler = create_test_trick_or_treat_handler()

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

        # Mock _adjust_ingots to return new total
        handler._adjust_ingots = AsyncMock(return_value=3000)
        # Mock _get_user_info to return nickname and ingots
        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.MONSTER, 1, outcomes, labels
        )

        # Verify ingots were removed (negative amount)
        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args
        self.assertEqual(call_args[0][1], -2000)  # Amount removed
        self.assertEqual(
            call_args.kwargs["reason"], "Trick or treat: backrooms entity"
        )

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.MemberService")
    async def test_process_door_choice_escape(
        self, mock_member_service_class, mock_db
    ):
        """Test escape door outcome (no ingot change)."""
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

        # Mock _adjust_ingots (should not be called for escape)
        handler._adjust_ingots = AsyncMock()
        # Mock _get_user_info to return nickname and ingots
        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.ESCAPE, 2, outcomes, labels
        )

        # Verify ingots were NOT adjusted
        handler._adjust_ingots.assert_not_called()

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.MemberService")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.choice")
    async def test_process_door_choice_monster_no_ingots(
        self, mock_choice, mock_randint, mock_member_service_class, mock_db
    ):
        """Test monster door when user has no ingots - should get lucky escape message."""
        mock_randint.return_value = 2000
        mock_choice.return_value = "Lucky escape message"

        handler = create_test_trick_or_treat_handler()

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

        # Mock _adjust_ingots to return None (user has no ingots)
        handler._adjust_ingots = AsyncMock(return_value=None)
        # Mock _get_user_info to return nickname and ingots
        handler._get_user_info = AsyncMock(return_value=("TestUser", 0))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.MONSTER, 1, outcomes, labels
        )

        # Verify ingots adjustment was attempted
        handler._adjust_ingots.assert_called_once()

        # Verify lucky escape message was chosen
        mock_choice.assert_called()

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    async def test_backrooms_view_timeout(self):
        """Test that view timeout sends expired message."""
        handler = create_test_trick_or_treat_handler()
        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🟨 Yellow Hallway", "💡 Buzzing Lights", "🚪 Empty Room"]

        view = BackroomsView(handler, self.test_user.id, outcomes, labels)
        view.message = MagicMock()
        view.message.edit = AsyncMock()

        await view.on_timeout()

        # Verify message was edited with expired message
        view.message.edit.assert_called_once()
        call_kwargs = view.message.edit.call_args.kwargs
        self.assertIn("embed", call_kwargs)
        self.assertIsNone(call_kwargs["view"])


if __name__ == "__main__":
    unittest.main()
