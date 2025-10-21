import asyncio
import json
import unittest
from collections import deque
from typing import Counter
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    CONTENT_FILE,
    TrickOrTreat,
)
from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
    TrickOrTreatHandler,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    MOCK_TRICK_OR_TREAT_DATA,
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    get_url_status_code,
    setup_database_service_mocks,
)


class TestTrickOrTreatHandler(unittest.IsolatedAsyncioTestCase):
    """Test cases for the core TrickOrTreatHandler functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_init(self):
        """Test that TrickOrTreatHandler initializes with empty history."""
        handler = create_test_trick_or_treat_handler()

        self.assertIsInstance(handler.history, dict)
        self.assertIn("gif", handler.history)
        self.assertIn("thumbnail", handler.history)
        self.assertIn("backrooms_thumbnail", handler.history)
        self.assertIn("positive_message", handler.history)
        self.assertIn("negative_message", handler.history)
        self.assertIn("quiz_question", handler.history)
        self.assertIn("joke", handler.history)

        for key, history_deque in handler.history.items():
            self.assertIsInstance(history_deque, deque)
            self.assertEqual(len(history_deque), 0)

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_add_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successfully adding ingots to a player."""
        handler = create_test_trick_or_treat_handler()

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
            self.test_user.id, 500, None, "Trick or treat: win"
        )

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_remove_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successfully removing ingots from a player."""
        handler = create_test_trick_or_treat_handler()

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

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    @patch(
        "ironforgedbot.commands.trickortreat.trick_or_treat_handler.send_error_response"
    )
    async def test_adjust_ingots_member_has_zero_ingots(
        self,
        mock_send_error,
        mock_member_service_class,
        mock_ingot_service_class,
        mock_db,
    ):
        """Test that removing ingots from a player with 0 ingots returns None."""
        handler = create_test_trick_or_treat_handler()

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

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_caps_removal_at_balance(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test that trying to remove more ingots than balance only removes available amount."""
        handler = create_test_trick_or_treat_handler()

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

        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            self.test_user.id, -100, None, "Trick or treat: loss"
        )
        self.assertEqual(result, 0)

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_handle_ingot_result_positive(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test _handle_ingot_result with a positive outcome."""
        handler = create_test_trick_or_treat_handler()

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

        handler._adjust_ingots = AsyncMock(return_value=1500)

        await handler._handle_ingot_result(self.interaction, 500, is_positive=True)

        self.interaction.followup.send.assert_called_once()
        call_args = self.interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]
        self.assertIsNotNone(embed)

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_handle_ingot_result_no_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test _handle_ingot_result when player has no ingots."""
        handler = create_test_trick_or_treat_handler()

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

        handler._adjust_ingots = AsyncMock(return_value=None)

        await handler._handle_ingot_result(self.interaction, -500, is_positive=False)

        self.interaction.followup.send.assert_called_once()

    # Media validation tests
    async def test_unique_gifs(self):
        """Test that all GIFs in the data file are unique."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            GIFS = data["media"]["gifs"]

        duplicates = [gif for gif, count in Counter(GIFS).items() if count > 1]
        assert not duplicates, f"Duplicate gifs: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_gifs_return_200(self):
        """Test that all GIF URLs are accessible (returns 200)."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            GIFS = data["media"]["gifs"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in GIFS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(GIFS, results):
                assert result == 200, f"{url} returned status code {result}"

    async def test_unique_thumbnails(self):
        """Test that all thumbnails in the data file are unique."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            THUMBNAILS = data["media"]["thumbnails"]

        duplicates = [
            thumb for thumb, count in Counter(THUMBNAILS).items() if count > 1
        ]
        assert not duplicates, f"Duplicate thumbnails: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_thumbnails_return_200(self):
        """Test that all thumbnail URLs are accessible (returns 200)."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            THUMBNAILS = data["media"]["thumbnails"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in THUMBNAILS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(THUMBNAILS, results):
                assert result == 200, f"{url} returned status code {result}"
