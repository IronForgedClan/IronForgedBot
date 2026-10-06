import json
import unittest
from datetime import datetime as datetime_type, timezone
from unittest.mock import patch

from ironforgedbot.state import BotState


class _AsyncTextFile:
    def __init__(self, content: str):
        self.content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def read(self):
        return self.content


class TestBotState(unittest.IsolatedAsyncioTestCase):
    def _create_state(self) -> BotState:
        state = object.__new__(BotState)
        state._file_path = "state.json"
        state.state = {
            "is_shutting_down": False,
            "rate_limit": {},
            "trick_or_treat_jackpot_claimed": False,
            "trick_or_treat_jackpot_year": 2026,
            "double_or_nothing_offers": {},
            "raffle_on": False,
            "raffle_price": 5000,
        }
        return state

    @patch("ironforgedbot.state.os.path.exists", return_value=True)
    @patch("ironforgedbot.state.aiofiles.open")
    @patch("ironforgedbot.state.datetime", create=True)
    async def test_load_state_resets_jackpot_for_new_utc_year(
        self, mock_datetime, mock_open, mock_exists
    ):
        state = self._create_state()
        saved_state = dict(state.state)
        saved_state["trick_or_treat_jackpot_claimed"] = True
        saved_state["trick_or_treat_jackpot_year"] = 2025
        mock_datetime.now.return_value = datetime_type(2026, 1, 1, tzinfo=timezone.utc)
        mock_open.return_value = _AsyncTextFile(json.dumps(saved_state))

        await state.load_state()

        self.assertFalse(state.state["trick_or_treat_jackpot_claimed"])
        self.assertEqual(state.state["trick_or_treat_jackpot_year"], 2026)
        self.assertEqual(state.state["raffle_price"], 5000)

    @patch("ironforgedbot.state.os.path.exists", return_value=True)
    @patch("ironforgedbot.state.aiofiles.open")
    @patch("ironforgedbot.state.datetime", create=True)
    async def test_load_state_preserves_claim_within_same_year(
        self, mock_datetime, mock_open, mock_exists
    ):
        state = self._create_state()
        saved_state = dict(state.state)
        saved_state["trick_or_treat_jackpot_claimed"] = True
        mock_datetime.now.return_value = datetime_type(2026, 10, 1, tzinfo=timezone.utc)
        mock_open.return_value = _AsyncTextFile(json.dumps(saved_state))

        await state.load_state()

        self.assertTrue(state.state["trick_or_treat_jackpot_claimed"])
        self.assertEqual(state.state["trick_or_treat_jackpot_year"], 2026)

    @patch("ironforgedbot.state.os.path.exists", return_value=True)
    @patch("ironforgedbot.state.aiofiles.open")
    @patch("ironforgedbot.state.datetime", create=True)
    async def test_load_state_migrates_legacy_file_and_resets_claim(
        self, mock_datetime, mock_open, mock_exists
    ):
        state = self._create_state()
        legacy_state = dict(state.state)
        legacy_state.pop("trick_or_treat_jackpot_year")
        legacy_state["trick_or_treat_jackpot_claimed"] = True
        legacy_state["raffle_on"] = True
        mock_datetime.now.return_value = datetime_type(2026, 10, 1, tzinfo=timezone.utc)
        mock_open.return_value = _AsyncTextFile(json.dumps(legacy_state))

        await state.load_state()

        self.assertFalse(state.state["trick_or_treat_jackpot_claimed"])
        self.assertEqual(state.state["trick_or_treat_jackpot_year"], 2026)
        self.assertTrue(state.state["raffle_on"])
