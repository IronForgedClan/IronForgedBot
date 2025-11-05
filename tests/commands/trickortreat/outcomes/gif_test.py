import unittest
from collections import deque

from ironforgedbot.commands.trickortreat.outcomes import gif
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_trick_or_treat_handler,
)


class TestGifOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for GIF outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_gif_outcome(self):
        """Test that GIF outcome sends a GIF."""
        handler = create_test_trick_or_treat_handler()
        handler.gifs = ["http://test.com/gif1.gif", "http://test.com/gif2.gif"]

        await gif.result_gif(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        gif_url = self.interaction.followup.send.call_args[0][0]
        self.assertTrue(gif_url.startswith("http"))

    async def test_gif_history_tracking(self):
        """Test that GIF history prevents recent repeats."""
        handler = create_test_trick_or_treat_handler()
        handler.gifs = [f"http://test.com/gif{i}.gif" for i in range(10)]
        handler.history["gif"] = deque()

        for _ in range(3):
            self.interaction.followup.send.reset_mock()
            await gif.result_gif(handler, self.interaction)
            sent_gif = self.interaction.followup.send.call_args[0][0]
            sent_gif_index = handler.gifs.index(sent_gif)
            self.assertIn(sent_gif_index, handler.history["gif"])

        self.assertEqual(len(handler.history["gif"]), 3)
