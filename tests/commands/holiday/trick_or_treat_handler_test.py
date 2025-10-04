import asyncio
import json
import unittest
from typing import Counter
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import discord

from ironforgedbot.commands.holiday.trick_or_treat_handler import (
    HIGH_INGOT_MAX,
    HIGH_INGOT_MIN,
    LOW_INGOT_MAX,
    LOW_INGOT_MIN,
    TrickOrTreat,
    TrickOrTreatHandler,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    get_url_status_code,
    setup_database_service_mocks,
)


class TestTrickOrTreatHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)
        self.interaction.guild = MagicMock()
        self.interaction.guild.get_member = MagicMock(return_value=self.test_user)

    async def test_init(self):
        """Test that TrickOrTreatHandler initializes with correct weights and empty history."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data='{"GIFS": [], "THUMBNAILS": []}'),
        ):
            handler = TrickOrTreatHandler()
            expected_weights = [1 / item.value for item in TrickOrTreat]

            self.assertEqual(handler.gif_history, [])
            self.assertEqual(handler.thumbnail_history, [])
            self.assertEqual(handler.positive_message_history, [])
            self.assertEqual(handler.negative_message_history, [])
            self.assertEqual(handler.weights, expected_weights)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_add_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successfully adding ingots to a player."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data='{"GIFS": [], "THUMBNAILS": []}'),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, _ = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 1500
        mock_ingot_service.try_add_ingots = AsyncMock(return_value=mock_result)

        result = await handler._adjust_ingots(self.interaction, 500, self.test_user)

        self.assertEqual(result, 1500)
        mock_ingot_service.try_add_ingots.assert_called_once_with(
            self.test_user.id, 500, None, "Trick or treat win"
        )

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_remove_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successfully removing ingots from a player."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data='{"GIFS": [], "THUMBNAILS": []}'),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 500
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)

        result = await handler._adjust_ingots(self.interaction, -500, self.test_user)

        self.assertEqual(result, 500)
        mock_ingot_service.try_remove_ingots.assert_called_once()

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.send_error_response")
    async def test_adjust_ingots_member_has_zero_ingots(
        self,
        mock_send_error,
        mock_member_service_class,
        mock_ingot_service_class,
        mock_db,
    ):
        """Test that removing ingots from a player with 0 ingots returns None."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data='{"GIFS": [], "THUMBNAILS": []}'),
        ):
            handler = TrickOrTreatHandler()

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

        result = await handler._adjust_ingots(self.interaction, -500, self.test_user)

        self.assertIsNone(result)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_caps_removal_at_balance(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test that trying to remove more ingots than balance only removes available amount."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data='{"GIFS": [], "THUMBNAILS": []}'),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=100,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 0
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)

        result = await handler._adjust_ingots(self.interaction, -500, self.test_user)

        # Should cap the removal at the member's balance
        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            self.test_user.id, -100, None, "Trick or treat loss"
        )
        self.assertEqual(result, 0)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    async def test_handle_ingot_result_positive(
        self, mock_ingot_service_class, mock_db
    ):
        """Test _handle_ingot_result with a positive outcome."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"GIFS": [], "THUMBNAILS": ["http://test.com/img.png"]}'
            ),
        ):
            handler = TrickOrTreatHandler()

        # Mock _adjust_ingots to return a successful balance
        handler._adjust_ingots = AsyncMock(return_value=1500)

        await handler._handle_ingot_result(self.interaction, 500, is_positive=True)

        self.interaction.followup.send.assert_called_once()
        call_args = self.interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]
        self.assertIsNotNone(embed)

    async def test_handle_ingot_result_no_ingots(self):
        """Test _handle_ingot_result when player has no ingots."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"GIFS": [], "THUMBNAILS": ["http://test.com/img.png"]}'
            ),
        ):
            handler = TrickOrTreatHandler()

        # Mock _adjust_ingots to return None (no ingots)
        handler._adjust_ingots = AsyncMock(return_value=None)

        await handler._handle_ingot_result(self.interaction, -500, is_positive=False)

        self.interaction.followup.send.assert_called_once()

    async def test_result_add_low(self):
        """Test result_add_low generates correct ingot range."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"GIFS": [], "THUMBNAILS": ["http://test.com/img.png"]}'
            ),
        ):
            handler = TrickOrTreatHandler()

        handler._handle_ingot_result = AsyncMock()

        await handler.result_add_low(self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertGreaterEqual(quantity, LOW_INGOT_MIN)
        self.assertLess(quantity, LOW_INGOT_MAX)
        self.assertTrue(is_positive)

    async def test_result_remove_high(self):
        """Test result_remove_high generates correct ingot range."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"GIFS": [], "THUMBNAILS": ["http://test.com/img.png"]}'
            ),
        ):
            handler = TrickOrTreatHandler()

        handler._handle_ingot_result = AsyncMock()

        await handler.result_remove_high(self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertLessEqual(quantity, -HIGH_INGOT_MIN)
        self.assertGreater(quantity, -HIGH_INGOT_MAX)
        self.assertFalse(is_positive)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.STATE")
    async def test_result_jackpot_already_claimed(self, mock_state):
        """Test that jackpot shows consolation message when already claimed."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"GIFS": [], "THUMBNAILS": ["http://test.com/img.png"]}'
            ),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": True}

        await handler.result_jackpot(self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("unworthy", embed.description.lower())

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.STATE")
    async def test_result_jackpot_success(self, mock_state):
        """Test successful jackpot claim."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data='{"GIFS": [], "THUMBNAILS": ["http://test.com/img.png"]}'
            ),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": False}
        handler._adjust_ingots = AsyncMock(return_value=1_500_000)

        await handler.result_jackpot(self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("JACKPOT", embed.description)
        self.assertTrue(mock_state.state["trick_or_treat_jackpot_claimed"])

    async def test_unique_gifs(self):
        """Test that all GIFs in the data file are unique."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            GIFS = data["GIFS"]

        duplicates = [gif for gif, count in Counter(GIFS).items() if count > 1]
        assert not duplicates, f"Duplicate gifs: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_gifs_return_200(self):
        """Test that all GIF URLs are accessible (returns 200)."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            GIFS = data["GIFS"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in GIFS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(GIFS, results):
                assert result == 200, f"{url} returned status code {result}"

    async def test_unique_thumbnails(self):
        """Test that all thumbnails in the data file are unique."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            THUMBNAILS = data["THUMBNAILS"]

        duplicates = [gif for gif, count in Counter(THUMBNAILS).items() if count > 1]
        assert not duplicates, f"Duplicate thumbnails: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_thumbnails_return_200(self):
        """Test that all thumbnail URLs are accessible (returns 200)."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            THUMBNAILS = data["THUMBNAILS"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in THUMBNAILS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(THUMBNAILS, results):
                assert result == 200, f"{url} returned status code {result}"
