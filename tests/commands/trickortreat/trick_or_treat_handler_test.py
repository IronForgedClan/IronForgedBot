import asyncio
import json
import os
import re
import unittest
from collections import deque
from typing import Counter
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import aiohttp

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    BACKROOMS_DOOR_COUNT,
    CONTENT_FILE,
    TrickOrTreat,
)
from ironforgedbot.commands.trickortreat import trick_or_treat_handler as handler_module
from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
    TrickOrTreatHandler,
)
from ironforgedbot.commands.trickortreat.types import (
    IngotAdjustment,
    IngotAdjustmentFailure,
    QUIZ_OPTION_COUNT,
)
from ironforgedcore.common.ranks import RANK
from ironforgedcore.common.roles import ROLE
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
        self.assertIn("backrooms_messages", handler.history)
        self.assertIn("positive_message", handler.history)
        self.assertIn("negative_message", handler.history)
        self.assertIn("quiz_question", handler.history)
        self.assertIn("joke", handler.history)

        for key, history_deque in handler.history.items():
            if key == "backrooms_messages":
                for category_history in history_deque.values():
                    self.assertIsInstance(category_history, deque)
                    self.assertEqual(len(category_history), 0)
            else:
                self.assertIsInstance(history_deque, deque)
                self.assertEqual(len(history_deque), 0)

    def test_backrooms_message_history_avoids_repeats_until_pool_exhausted(self):
        handler = create_test_trick_or_treat_handler()
        messages = ["first", "second", "third"]

        with patch(
            "ironforgedbot.commands.trickortreat.trick_or_treat_handler.random.choice",
            side_effect=lambda choices: choices[0],
        ):
            first_intro = handler._get_backrooms_message("intro", messages)
            first_escape = handler._get_backrooms_message("escape", messages)
            later_intro = [
                handler._get_backrooms_message("intro", messages) for _ in range(3)
            ]

        self.assertEqual(first_intro, "first")
        self.assertEqual(first_escape, "first")
        self.assertEqual(later_intro, ["second", "third", "first"])

    async def test_random_result_dispatches_every_outcome(self):
        handler = create_test_trick_or_treat_handler()
        outcome_handlers = {
            TrickOrTreat.JACKPOT_INGOTS: "jackpot.result_jackpot",
            TrickOrTreat.REMOVE_ALL_INGOTS_TRICK: "trick.result_remove_all_ingots_trick",
            TrickOrTreat.DOUBLE_OR_NOTHING: "double_or_nothing.result_double_or_nothing",
            TrickOrTreat.STEAL: "steal.result_steal",
            TrickOrTreat.QUIZ_MASTER: "quiz_master.result_quiz_master",
            TrickOrTreat.BACKROOMS: "backrooms.result_backrooms",
            TrickOrTreat.REMOVE_INGOTS_HIGH: "ingot_changes.result_remove_high",
            TrickOrTreat.ADD_INGOTS_HIGH: "ingot_changes.result_add_high",
            TrickOrTreat.REMOVE_INGOTS_LOW: "ingot_changes.result_remove_low",
            TrickOrTreat.ADD_INGOTS_LOW: "ingot_changes.result_add_low",
            TrickOrTreat.JOKE: "joke.result_joke",
            TrickOrTreat.GIF: "gif.result_gif",
        }

        self.assertEqual(set(outcome_handlers), set(TrickOrTreat))
        for outcome, handler_path in outcome_handlers.items():
            with self.subTest(outcome=outcome):
                with patch(
                    f"ironforgedbot.commands.trickortreat.outcomes.{handler_path}",
                    new_callable=AsyncMock,
                ) as mock_outcome:
                    with patch(
                        "ironforgedbot.commands.trickortreat.trick_or_treat_handler.random.choices",
                        return_value=[outcome],
                    ):
                        await handler.random_result(self.interaction)

                mock_outcome.assert_awaited_once_with(handler, self.interaction)

    def test_get_handler_returns_cached_instance(self):
        with patch.object(handler_module, "_handler_instance", None):
            with patch.object(handler_module, "TrickOrTreatHandler") as handler_class:
                first = handler_module.get_handler()
                second = handler_module.get_handler()

        self.assertIs(first, second)
        handler_class.assert_called_once_with()

    def test_get_random_from_list_avoids_recent_items_and_resets_history(self):
        handler = create_test_trick_or_treat_handler()
        history = deque(maxlen=5)

        with patch(
            "ironforgedbot.commands.trickortreat.trick_or_treat_handler.random.choice",
            side_effect=lambda available: available[0],
        ):
            results = [
                handler._get_random_from_list(["A", "B"], history) for _ in range(3)
            ]

        self.assertEqual(results, ["A", "B", "A"])
        self.assertEqual(list(history), [0])

    def test_get_random_from_list_rejects_empty_items(self):
        handler = create_test_trick_or_treat_handler()

        with self.assertRaisesRegex(ValueError, "non-empty"):
            handler._get_random_from_list([], deque())

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

        self.assertEqual(result.new_total, 1500)
        self.assertEqual(result.applied_quantity, 500)
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

        self.assertEqual(result.new_total, 500)
        self.assertEqual(result.applied_quantity, -500)
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

        self.assertEqual(result.failure, IngotAdjustmentFailure.NO_INGOTS)

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
        self.assertEqual(result.new_total, 0)
        self.assertEqual(result.applied_quantity, -100)

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

        handler._adjust_ingots = AsyncMock(return_value=IngotAdjustment(1500, 500))

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

        handler._adjust_ingots = AsyncMock(
            return_value=IngotAdjustment(None, 0, IngotAdjustmentFailure.NO_INGOTS)
        )

        await handler._handle_ingot_result(self.interaction, -500, is_positive=False)

        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_handle_ingot_result_displays_capped_loss(
        self, mock_member_service_class, mock_db
    ):
        handler = create_test_trick_or_treat_handler()
        setup_database_service_mocks(mock_db, mock_member_service_class)
        handler._adjust_ingots = AsyncMock(return_value=IngotAdjustment(0, -100))

        await handler._handle_ingot_result(self.interaction, -500, is_positive=False)

        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("-100", embed.description)
        self.assertNotIn("-500", embed.description)

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_handle_ingot_result_does_not_duplicate_adjustment_error(
        self, mock_member_service_class, mock_db
    ):
        handler = create_test_trick_or_treat_handler()
        setup_database_service_mocks(mock_db, mock_member_service_class)
        handler._adjust_ingots = AsyncMock(
            return_value=IngotAdjustment(None, 0, IngotAdjustmentFailure.ERROR)
        )

        await handler._handle_ingot_result(self.interaction, -500, is_positive=False)

        self.interaction.followup.send.assert_not_called()

    # Media validation tests
    async def test_unique_gifs(self):
        """Test that all GIFs in the data file are unique."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            GIFS = data["media"]["gifs"]

        duplicates = [gif for gif, count in Counter(GIFS).items() if count > 1]
        assert not duplicates, f"Duplicate gifs: {duplicates}"

    @unittest.skipUnless(
        os.getenv("RUN_NETWORK_TESTS") == "1",
        "Network heavy test, set RUN_NETWORK_TESTS=1 to run",
    )
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

    @unittest.skipUnless(
        os.getenv("RUN_NETWORK_TESTS") == "1",
        "Network heavy test, set RUN_NETWORK_TESTS=1 to run",
    )
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

    async def test_unique_backrooms_thumbnails(self):
        """Test that all backrooms thumbnails are unique."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            BACKROOMS_THUMBNAILS = data["backrooms"]["thumbnails"]

        duplicates = [
            thumb for thumb, count in Counter(BACKROOMS_THUMBNAILS).items() if count > 1
        ]
        assert not duplicates, f"Duplicate backrooms thumbnails: {duplicates}"

    @unittest.skipUnless(
        os.getenv("RUN_NETWORK_TESTS") == "1",
        "Network heavy test, set RUN_NETWORK_TESTS=1 to run",
    )
    async def test_backrooms_thumbnails_return_200(self):
        """Test that all backrooms thumbnail URLs are accessible (returns 200)."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            BACKROOMS_THUMBNAILS = data["backrooms"]["thumbnails"]
            SUSPENSE_THUMBNAIL = data["backrooms"]["suspense_thumbnail"]

        all_urls = BACKROOMS_THUMBNAILS + [SUSPENSE_THUMBNAIL]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in all_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(all_urls, results):
                assert result == 200, f"{url} returned status code {result}"

    async def test_quiz_questions_structure(self):
        """Test that all quiz questions have valid structure."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            QUESTIONS = data["quiz_master"]["questions"]

        assert len(QUESTIONS) > 0, "Quiz master should have at least one question"

        for i, question in enumerate(QUESTIONS):
            assert (
                "question" in question
            ), f"Question {i} missing 'question' field: {question}"
            assert (
                "options" in question
            ), f"Question {i} missing 'options' field: {question}"
            assert (
                "correct_index" in question
            ), f"Question {i} missing 'correct_index' field: {question}"

            assert isinstance(
                question["question"], str
            ), f"Question {i} 'question' must be a string"
            assert (
                len(question["question"]) > 0
            ), f"Question {i} 'question' cannot be empty"

            options = question["options"]
            assert isinstance(options, list), f"Question {i} 'options' must be a list"
            assert (
                len(options) == QUIZ_OPTION_COUNT
            ), f"Question {i} must have exactly {QUIZ_OPTION_COUNT} options, got {len(options)}"

            for j, option in enumerate(options):
                assert isinstance(
                    option, dict
                ), f"Question {i}, option {j} must be a dict"
                assert (
                    "text" in option
                ), f"Question {i}, option {j} missing 'text' field"
                assert isinstance(
                    option["text"], str
                ), f"Question {i}, option {j} 'text' must be a string"
                assert (
                    len(option["text"]) > 0
                ), f"Question {i}, option {j} 'text' cannot be empty"

            correct_index = question["correct_index"]
            assert isinstance(
                correct_index, int
            ), f"Question {i} 'correct_index' must be an integer"
            assert (
                0 <= correct_index < len(options)
            ), f"Question {i} 'correct_index' {correct_index} out of range [0, {len(options)})"

    async def test_unique_door_labels(self):
        """Test that all backrooms door labels are unique."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            DOOR_LABELS = data["backrooms"]["door_labels"]

        duplicates = [
            label for label, count in Counter(DOOR_LABELS).items() if count > 1
        ]
        assert not duplicates, f"Duplicate door labels: {duplicates}"

    async def test_sufficient_door_labels(self):
        """Test that there are at least 3 door labels for backrooms."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            DOOR_LABELS = data["backrooms"]["door_labels"]

        assert (
            len(DOOR_LABELS) >= 3
        ), f"Backrooms needs at least 3 door labels, got {len(DOOR_LABELS)}"

    async def test_door_labels_are_non_empty_strings(self):
        """Test that all door labels are non-empty strings."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            DOOR_LABELS = data["backrooms"]["door_labels"]

        for i, label in enumerate(DOOR_LABELS):
            assert isinstance(label, str), f"Door label {i} must be a string: {label}"
            assert len(label) > 0, f"Door label {i} cannot be empty"

    async def test_positive_messages_valid(self):
        """Test that positive messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["general"]["positive_messages"]

        assert len(MESSAGES) > 0, "Must have at least one positive message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Positive message {i} must be a string"
            assert len(msg) > 0, f"Positive message {i} cannot be empty"
            assert (
                "{ingots}" in msg
            ), f"Positive message {i} missing {{ingots}} placeholder"

    async def test_negative_messages_valid(self):
        """Test that negative messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["general"]["negative_messages"]

        assert len(MESSAGES) > 0, "Must have at least one negative message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Negative message {i} must be a string"
            assert len(msg) > 0, f"Negative message {i} cannot be empty"
            assert (
                "{ingots}" in msg
            ), f"Negative message {i} missing {{ingots}} placeholder"

    async def test_backrooms_treasure_messages_valid(self):
        """Test that backrooms treasure messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["backrooms"]["treasure_messages"]

        assert len(MESSAGES) > 0, "Must have at least one treasure message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Treasure message {i} must be a string"
            assert len(msg) > 0, f"Treasure message {i} cannot be empty"
            assert (
                "{ingots}" not in msg
            ), f"Treasure message {i} duplicates structured reward amount"

    async def test_backrooms_escapable_monster_messages_valid(self):
        """Test monster messages leave haul totals to embed fields."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["backrooms"]["monster_messages"]

        assert len(MESSAGES) > 0, "Must have at least one escapable monster message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(
                msg, str
            ), f"Escapable monster message {i} must be a string"
            assert len(msg) > 0, f"Escapable monster message {i} cannot be empty"
            assert "{lost}" not in msg
            assert "{pot}" not in msg

    async def test_backrooms_fatal_monster_messages_valid(self):
        """Test fatal monster messages leave losses to embed fields."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            messages = data["backrooms"]["fatal_monster_messages"]

        assert messages, "Must have at least one fatal monster message"
        for i, msg in enumerate(messages):
            assert isinstance(msg, str), f"Fatal monster message {i} must be a string"
            assert "{ingots}" not in msg

    async def test_backrooms_escape_messages_valid(self):
        """Test that backrooms escape messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["backrooms"]["escape_messages"]

        assert len(MESSAGES) > 0, "Must have at least one escape message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Escape message {i} must be a string"
            assert len(msg) > 0, f"Escape message {i} cannot be empty"

    async def test_backrooms_bargain_message_has_no_run_placeholders(self):
        """Test bargain message leaves values and progression to embed fields."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            messages = data["backrooms"]["bargain_messages"]

        for message in messages:
            for placeholder in ("{room}", "{lost}", "{bonus}", "{pot}"):
                assert placeholder not in message

    async def test_backrooms_content_pools_meet_variety_targets(self):
        targets = {
            "intro_messages": 5,
            "continue_intro_messages": 8,
            "door_labels": 24,
            "treasure_messages": 24,
            "fatal_monster_messages": 12,
            "monster_messages": 18,
            "escape_messages": 24,
            "bargain_messages": 10,
            "opening_door_messages": 10,
            "expired_messages": 5,
        }
        with open(CONTENT_FILE) as f:
            content_data = json.load(f)
            backrooms_data = content_data["backrooms"]

        for key, minimum_count in targets.items():
            with self.subTest(content_pool=key):
                messages = backrooms_data[key]
                self.assertGreaterEqual(len(messages), minimum_count)
                self.assertEqual(len(set(messages)), len(messages))
        TrickOrTreatHandler._validate_content_data(content_data, CONTENT_FILE)

    async def test_backrooms_copy_has_no_room_numbers_or_unexpected_placeholders(self):
        message_pools = (
            "intro_messages",
            "continue_intro_messages",
            "door_labels",
            "treasure_messages",
            "fatal_monster_messages",
            "monster_messages",
            "escape_messages",
            "bargain_messages",
            "opening_door_messages",
            "expired_messages",
        )
        with open(CONTENT_FILE) as f:
            backrooms_data = json.load(f)["backrooms"]

        for pool_name in message_pools:
            for message in backrooms_data[pool_name]:
                with self.subTest(content_pool=pool_name, message=message):
                    self.assertNotRegex(
                        message,
                        r"(?i)\broom\s+(?:one|two|three|four|five|\d+)\b",
                    )
                    if pool_name == "opening_door_messages":
                        message.format(door="Test Door")
                    else:
                        message.format()

    async def test_joke_messages_valid(self):
        """Test that joke messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["joke"]["messages"]

        assert len(MESSAGES) > 0, "Must have at least one joke"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Joke message {i} must be a string"
            assert len(msg) > 0, f"Joke message {i} cannot be empty"


class TestLoadContentFile(unittest.TestCase):
    """Test cases for the _load_content_file method."""

    def test_load_content_file_success(self):
        """Test successfully loading a valid content file."""
        valid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        mock_file = mock_open(read_data=json.dumps(valid_data))

        with patch("builtins.open", mock_file):
            result = TrickOrTreatHandler._load_content_file("test_path.json")

        self.assertEqual(result, valid_data)
        mock_file.assert_called_once_with("test_path.json")

    def test_load_content_file_not_found(self):
        """Test that FileNotFoundError is raised when file doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError("test.json")):
            with self.assertRaises(FileNotFoundError) as context:
                TrickOrTreatHandler._load_content_file("missing.json")

        self.assertIn("Trick-or-treat content file not found", str(context.exception))
        self.assertIn("missing.json", str(context.exception))

    def test_load_content_file_invalid_json(self):
        """Test that ValueError is raised for invalid JSON syntax."""
        mock_file = mock_open(read_data="{invalid json")

        with patch("builtins.open", mock_file):
            with self.assertRaises(ValueError) as context:
                TrickOrTreatHandler._load_content_file("invalid.json")

        self.assertIn("Invalid JSON syntax", str(context.exception))

    def test_load_content_file_missing_keys(self):
        """Test that KeyError is raised when required keys are missing."""
        incomplete_data = {"jackpot": {}, "media": {}}
        mock_file = mock_open(read_data=json.dumps(incomplete_data))

        with patch("builtins.open", mock_file):
            with self.assertRaises(KeyError) as context:
                TrickOrTreatHandler._load_content_file("incomplete.json")

        error_msg = str(context.exception)
        self.assertIn("Missing required keys", error_msg)
        self.assertIn("double_or_nothing", error_msg)
        self.assertIn("steal", error_msg)

    def test_load_content_file_rejects_quiz_with_fewer_than_four_options(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        invalid_data["quiz_master"]["questions"][0]["options"] = [
            {"text": "A"},
            {"text": "B"},
            {"text": "C"},
        ]
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "exactly 4 options"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_rejects_too_few_backrooms_door_labels(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        invalid_data["backrooms"]["door_labels"] = [
            "Door" for _ in range(BACKROOMS_DOOR_COUNT - 1)
        ]
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "at least"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_rejects_backrooms_weights_that_do_not_sum_to_one(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        invalid_data["backrooms"]["room_outcome_weights"]["2"]["treasure"] = 0.5
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "sum to 1"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_rejects_unknown_backrooms_outcomes(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        invalid_data["backrooms"]["room_outcome_weights"]["2"]["jackpot"] = 0.0
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "outcome"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_rejects_missing_backrooms_room_weights(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        del invalid_data["backrooms"]["room_outcome_weights"]["3"]
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "missing"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_rejects_negative_backrooms_weights(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        invalid_data["backrooms"]["room_outcome_weights"]["2"]["treasure"] = -0.1
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "probability"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_preserves_safe_first_room_weight(self):
        invalid_data = json.loads(MOCK_TRICK_OR_TREAT_DATA)
        invalid_data["backrooms"]["room_outcome_weights"]["1"] = {
            "treasure": 0.5,
            "escape": 0.5,
        }
        mock_file = mock_open(read_data=json.dumps(invalid_data))

        with patch("builtins.open", mock_file):
            with self.assertRaisesRegex(ValueError, "first room"):
                TrickOrTreatHandler._load_content_file("invalid.json")

    def test_load_content_file_unexpected_error(self):
        """Test that RuntimeError is raised for unexpected errors."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(RuntimeError) as context:
                TrickOrTreatHandler._load_content_file("test.json")

        self.assertIn(
            "Unexpected error loading trick-or-treat content", str(context.exception)
        )
