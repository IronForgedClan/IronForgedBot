import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from ironforgedbot.commands.trickortreat.outcomes import backrooms
from ironforgedbot.commands.trickortreat.outcomes.backrooms import (
    BackroomsView,
    DoorOutcome,
)
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_trick_or_treat_handler,
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

        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

        view = call_kwargs["view"]
        self.assertIsInstance(view, BackroomsView)

        self.assertIn("embed", call_kwargs)

    async def test_backrooms_view_has_three_doors(self):
        """Test that BackroomsView creates exactly 3 corridor buttons."""
        handler = create_test_trick_or_treat_handler()
        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🟨 Yellow Hallway", "💡 Buzzing Lights", "🚪 Empty Room"]

        view = BackroomsView(handler, self.test_user.id, outcomes, labels)

        self.assertEqual(len(view.children), 3)

        for button in view.children:
            self.assertEqual(button.row, 0)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_process_door_choice_treasure(self, mock_randint):
        """Test treasure door outcome."""
        mock_randint.return_value = 3000

        handler = create_test_trick_or_treat_handler()

        handler._adjust_ingots = AsyncMock(return_value=4500)
        handler._get_user_info = AsyncMock(return_value=("TestUser", 1500))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        result = await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.TREASURE, 0, outcomes, labels
        )

        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args
        self.assertEqual(call_args[0][1], 3000)
        self.assertEqual(
            call_args.kwargs["reason"], "Trick or treat: backrooms treasure"
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_process_door_choice_monster(self, mock_randint):
        """Test monster door outcome."""
        mock_randint.return_value = 2000

        handler = create_test_trick_or_treat_handler()

        handler._adjust_ingots = AsyncMock(return_value=3000)
        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        result = await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.MONSTER, 1, outcomes, labels
        )

        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args
        self.assertEqual(call_args[0][1], -2000)
        self.assertEqual(call_args.kwargs["reason"], "Trick or treat: backrooms entity")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)

    async def test_process_door_choice_escape(self):
        """Test escape door outcome (no ingot change)."""
        handler = create_test_trick_or_treat_handler()

        handler._adjust_ingots = AsyncMock()
        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        result = await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.ESCAPE, 2, outcomes, labels
        )

        handler._adjust_ingots.assert_not_called()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.choice")
    async def test_process_door_choice_monster_no_ingots(
        self, mock_choice, mock_randint
    ):
        """Test monster door when user has no ingots - should get lucky escape message."""
        mock_randint.return_value = 2000
        mock_choice.return_value = "Lucky escape message"

        handler = create_test_trick_or_treat_handler()

        handler._adjust_ingots = AsyncMock(return_value=None)
        handler._get_user_info = AsyncMock(return_value=("TestUser", 0))

        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🚪 Door 1", "🕸️ Door 2", "💀 Door 3"]

        result = await backrooms.process_door_choice(
            handler, self.interaction, DoorOutcome.MONSTER, 1, outcomes, labels
        )

        handler._adjust_ingots.assert_called_once()

        mock_choice.assert_called()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)

    async def test_backrooms_view_timeout(self):
        """Test that view timeout sends expired message."""
        handler = create_test_trick_or_treat_handler()
        outcomes = [DoorOutcome.TREASURE, DoorOutcome.MONSTER, DoorOutcome.ESCAPE]
        labels = ["🟨 Yellow Hallway", "💡 Buzzing Lights", "🚪 Empty Room"]

        view = BackroomsView(handler, self.test_user.id, outcomes, labels)
        view.message = MagicMock()
        view.message.edit = AsyncMock()

        await view.on_timeout()

        view.message.edit.assert_called_once()
        call_kwargs = view.message.edit.call_args.kwargs
        self.assertIn("embed", call_kwargs)
        self.assertIsNone(call_kwargs["view"])
