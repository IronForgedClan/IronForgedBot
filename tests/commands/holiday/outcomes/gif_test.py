"""Tests for the GIF outcome in trick-or-treat."""

import unittest

from ironforgedbot.commands.holiday.outcomes import gif
from ironforgedbot.common.roles import ROLE
from tests.commands.holiday.test_helpers import (
    create_test_handler,
    create_test_interaction,
)
from tests.helpers import create_test_member


class TestGifOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for GIF outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_test_interaction(user=self.test_user)

    async def test_gif_outcome(self):
        """Test that GIF outcome sends a GIF."""
        handler = create_test_handler()
        # Add a GIF to the handler's list
        handler.GIFS = ["http://test.com/gif1.gif", "http://test.com/gif2.gif"]

        await gif.result_gif(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        # Should send a GIF URL
        gif_url = self.interaction.followup.send.call_args[0][0]
        self.assertTrue(gif_url.startswith("http"))

    async def test_gif_history_tracking(self):
        """Test that GIF history prevents recent repeats."""
        handler = create_test_handler()
        handler.GIFS = [f"http://test.com/gif{i}.gif" for i in range(10)]
        handler.gif_history = []

        # Send multiple GIFs
        for _ in range(3):
            self.interaction.followup.send.reset_mock()
            await gif.result_gif(handler, self.interaction)
            sent_gif = self.interaction.followup.send.call_args[0][0]
            # Verify the sent GIF was added to history
            self.assertIn(sent_gif, handler.gif_history)

        # History should track recent GIFs
        self.assertEqual(len(handler.gif_history), 3)
