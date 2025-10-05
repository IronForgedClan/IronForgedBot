"""Tests for the ingot addition/removal outcomes in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock

from ironforgedbot.commands.holiday.outcomes import ingot_changes
from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    HIGH_INGOT_MIN,
    LOW_INGOT_MAX,
    LOW_INGOT_MIN,
)
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_trick_or_treat_handler,
)


class TestIngotChangesOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for ingot addition/removal outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_result_add_low(self):
        """Test result_add_low generates correct ingot range."""
        handler = create_test_trick_or_treat_handler()

        handler._handle_ingot_result = AsyncMock()

        await ingot_changes.result_add_low(handler, self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertGreaterEqual(quantity, LOW_INGOT_MIN)
        self.assertLess(quantity, LOW_INGOT_MAX)
        self.assertTrue(is_positive)

    async def test_result_remove_high(self):
        """Test result_remove_high generates correct ingot range."""
        handler = create_test_trick_or_treat_handler()

        handler._handle_ingot_result = AsyncMock()

        await ingot_changes.result_remove_high(handler, self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertLessEqual(quantity, -HIGH_INGOT_MIN)
        self.assertGreater(quantity, -HIGH_INGOT_MAX)
        self.assertFalse(is_positive)
