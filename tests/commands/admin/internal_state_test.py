import io
import json
import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.state import BotStateDict


class TestInternalState(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.default_state: BotStateDict = {
            "is_shutting_down": False,
            "rate_limit": {},
            "trick_or_treat_jackpot_claimed": False,
            "raffle_on": False,
            "raffle_price": 5000,
        }

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_default(self, mock_state):
        mock_state.state = self.default_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        self.assertIsInstance(result, discord.File)
        self.assertEqual(result.filename, "state.json")

        content = result.fp.read().decode("utf-8")
        parsed_content = json.loads(content)
        self.assertEqual(parsed_content, self.default_state)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_with_rate_limits(self, mock_state):
        state_with_rate_limits: BotStateDict = {
            "is_shutting_down": False,
            "rate_limit": {"user123": 1640995200, "user456": 1640995300},
            "trick_or_treat_jackpot_claimed": True,
            "raffle_on": True,
            "raffle_price": 10000,
        }
        mock_state.state = state_with_rate_limits

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        content = result.fp.read().decode("utf-8")
        parsed_content = json.loads(content)
        self.assertEqual(parsed_content, state_with_rate_limits)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_shutting_down(self, mock_state):
        shutting_down_state: BotStateDict = {
            "is_shutting_down": True,
            "rate_limit": {},
            "trick_or_treat_jackpot_claimed": False,
            "raffle_on": False,
            "raffle_price": 5000,
        }
        mock_state.state = shutting_down_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        content = result.fp.read().decode("utf-8")
        parsed_content = json.loads(content)
        self.assertEqual(parsed_content, shutting_down_state)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_json_formatting(self, mock_state):
        mock_state.state = self.default_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        content = result.fp.read().decode("utf-8")
        expected_content = json.dumps(self.default_state, indent=2)
        self.assertEqual(content, expected_content)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_file_position_reset(self, mock_state):
        mock_state.state = self.default_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        self.assertEqual(result.fp.tell(), 0)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_multiple_calls(self, mock_state):
        mock_state.state = self.default_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result1 = get_internal_state()
        result2 = get_internal_state()

        content1 = result1.fp.read().decode("utf-8")
        content2 = result2.fp.read().decode("utf-8")

        self.assertEqual(content1, content2)
        self.assertIsNot(result1, result2)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_complex_rate_limit_structure(self, mock_state):
        complex_state: BotStateDict = {
            "is_shutting_down": False,
            "rate_limit": {
                "user1": 1640995200,
                "user2": 1640995300,
                "user3": 1640995400,
            },
            "trick_or_treat_jackpot_claimed": True,
            "raffle_on": True,
            "raffle_price": 25000,
        }
        mock_state.state = complex_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        content = result.fp.read().decode("utf-8")
        parsed_content = json.loads(content)
        self.assertEqual(parsed_content, complex_state)
        self.assertEqual(len(parsed_content["rate_limit"]), 3)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_empty_rate_limit(self, mock_state):
        empty_rate_limit_state: BotStateDict = {
            "is_shutting_down": False,
            "rate_limit": {},
            "trick_or_treat_jackpot_claimed": False,
            "raffle_on": False,
            "raffle_price": 0,
        }
        mock_state.state = empty_rate_limit_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        content = result.fp.read().decode("utf-8")
        parsed_content = json.loads(content)
        self.assertEqual(parsed_content, empty_rate_limit_state)
        self.assertEqual(parsed_content["rate_limit"], {})

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_encoding_utf8(self, mock_state):
        mock_state.state = self.default_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        raw_bytes = result.fp.read()
        self.assertIsInstance(raw_bytes, bytes)

        decoded_content = raw_bytes.decode("utf-8")
        self.assertIsInstance(decoded_content, str)
        json.loads(decoded_content)

    @patch("ironforgedbot.commands.admin.internal_state.STATE")
    def test_get_internal_state_file_properties(self, mock_state):
        mock_state.state = self.default_state

        from ironforgedbot.commands.admin.internal_state import get_internal_state

        result = get_internal_state()

        self.assertEqual(result.filename, "state.json")
        self.assertIsInstance(result.fp, io.BytesIO)
