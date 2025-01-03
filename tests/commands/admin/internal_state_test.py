import io
import json
import unittest
from unittest.mock import patch

import discord

from ironforgedbot.commands.admin.internal_state import get_internal_state
from ironforgedbot.state import BotStateDict


class TestInternalState(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    async def test_internal_state(self, mock_state):
        """Test that method returns expected data"""
        expected_state: BotStateDict = {
            "is_shutting_down": False,
            "rate_limit": dict(),
            "trick_or_treat_jackpot_claimed": False,
        }
        mock_state.state = expected_state

        json_bytes = io.BytesIO(json.dumps(expected_state, indent=2).encode("utf-8"))
        json_bytes.seek(0)

        expected_file = discord.File(json_bytes, "state.json")
        actual_file = get_internal_state()

        expected_content = expected_file.fp.read()
        actual_content = actual_file.fp.read()

        self.assertEqual(expected_content, actual_content)
