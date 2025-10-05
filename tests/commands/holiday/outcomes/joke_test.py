"""Tests for the joke outcome in trick-or-treat."""

import unittest

from ironforgedbot.commands.holiday.outcomes import joke
from ironforgedbot.common.roles import ROLE
from tests.commands.holiday.test_helpers import (
    create_test_handler,
    create_test_interaction,
)
from tests.helpers import create_test_member


class TestJokeOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for joke outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_test_interaction(user=self.test_user)

    async def test_joke_outcome(self):
        """Test that joke outcome sends a random joke."""
        handler = create_test_handler()

        await joke.result_joke(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIsNotNone(embed.description)
