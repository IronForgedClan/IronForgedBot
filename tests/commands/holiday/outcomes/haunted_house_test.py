"""Tests for the haunted house outcome in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.commands.holiday.outcomes import haunted_house
from ironforgedbot.commands.holiday.outcomes.haunted_house import (
    DoorOutcome,
    HauntedHouseView,
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


class TestHauntedHouseOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for haunted house outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_result_haunted_house_creates_view(self):
        """Test that haunted house creates a view with door buttons."""
        handler = create_test_trick_or_treat_handler()

        await haunted_house.result_haunted_house(handler, self.interaction)

        # Verify a view was sent (has the door buttons)
        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

        # Verify it's a HauntedHouseView
        view = call_kwargs["view"]
        self.assertIsInstance(view, HauntedHouseView)

        # Verify embed was sent
        self.assertIn("embed", call_kwargs)

    def test_haunted_house_view_has_three_doors(self):
        """Test that HauntedHouseView creates exactly 3 door buttons."""
        handler = create_test_trick_or_treat_handler()
        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]

        view = HauntedHouseView(handler, self.test_user.id, outcomes)

        # Should have 3 buttons (one for each door)
        self.assertEqual(len(view.children), 3)

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.haunted_house.random.randint")
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

        await haunted_house.process_door_choice(
            handler, self.interaction, DoorOutcome.TREASURE
        )

        # Verify ingots were added
        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args
        self.assertEqual(call_args[0][1], 3000)  # Amount added
        self.assertEqual(
            call_args.kwargs["reason"], "Trick or treat: haunted house treasure"
        )

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.haunted_house.random.randint")
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

        await haunted_house.process_door_choice(
            handler, self.interaction, DoorOutcome.MONSTER
        )

        # Verify ingots were removed (negative amount)
        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args
        self.assertEqual(call_args[0][1], -2000)  # Amount removed
        self.assertEqual(
            call_args.kwargs["reason"], "Trick or treat: haunted house monster"
        )

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
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

        await haunted_house.process_door_choice(
            handler, self.interaction, DoorOutcome.ESCAPE
        )

        # Verify ingots were NOT adjusted
        handler._adjust_ingots.assert_not_called()

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.haunted_house.random.randint")
    async def test_process_door_choice_monster_no_ingots(
        self, mock_randint, mock_member_service_class, mock_db
    ):
        """Test monster door when user has no ingots."""
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
            ingots=0,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots to return None (user has no ingots)
        handler._adjust_ingots = AsyncMock(return_value=None)

        await haunted_house.process_door_choice(
            handler, self.interaction, DoorOutcome.MONSTER
        )

        # Verify ingots adjustment was attempted
        handler._adjust_ingots.assert_called_once()

        # Verify followup message was sent
        self.interaction.followup.send.assert_called_once()

    async def test_haunted_house_view_timeout(self):
        """Test that view timeout sends expired message."""
        handler = create_test_trick_or_treat_handler()
        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]

        view = HauntedHouseView(handler, self.test_user.id, outcomes)
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
