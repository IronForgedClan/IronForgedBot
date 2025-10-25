import asyncio
import json
import os
import unittest
from collections import deque
from typing import Counter
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import aiohttp

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import CONTENT_FILE
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

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in BACKROOMS_THUMBNAILS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(BACKROOMS_THUMBNAILS, results):
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
                len(options) >= 2
            ), f"Question {i} must have at least 2 options, got {len(options)}"

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
                "{ingots}" in msg
            ), f"Treasure message {i} missing {{ingots}} placeholder"

    async def test_backrooms_monster_messages_valid(self):
        """Test that backrooms monster messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["backrooms"]["monster_messages"]

        assert len(MESSAGES) > 0, "Must have at least one monster message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Monster message {i} must be a string"
            assert len(msg) > 0, f"Monster message {i} cannot be empty"
            assert (
                "{ingots}" in msg
            ), f"Monster message {i} missing {{ingots}} placeholder"

    async def test_backrooms_escape_messages_valid(self):
        """Test that backrooms escape messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["backrooms"]["escape_messages"]

        assert len(MESSAGES) > 0, "Must have at least one escape message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Escape message {i} must be a string"
            assert len(msg) > 0, f"Escape message {i} cannot be empty"

    async def test_backrooms_lucky_escape_messages_valid(self):
        """Test that backrooms lucky escape messages array is valid."""
        with open(CONTENT_FILE) as f:
            data = json.load(f)
            MESSAGES = data["backrooms"]["lucky_escape_messages"]

        assert len(MESSAGES) > 0, "Must have at least one lucky escape message"
        for i, msg in enumerate(MESSAGES):
            assert isinstance(msg, str), f"Lucky escape message {i} must be a string"
            assert len(msg) > 0, f"Lucky escape message {i} cannot be empty"

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

    def test_load_content_file_unexpected_error(self):
        """Test that RuntimeError is raised for unexpected errors."""
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with self.assertRaises(RuntimeError) as context:
                TrickOrTreatHandler._load_content_file("test.json")

        self.assertIn(
            "Unexpected error loading trick-or-treat content", str(context.exception)
        )
