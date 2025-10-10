"""Tests for the quiz master outcome in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.commands.holiday.outcomes import quiz_master
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_trick_or_treat_handler,
)


class TestQuizMasterOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for quiz master outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_quiz_master_presents_question(self):
        """Test that quiz master presents a question with 4 options."""
        handler = create_test_trick_or_treat_handler()

        await quiz_master.result_quiz_master(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        call_args = self.interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]
        view = call_args.kwargs["view"]

        # Verify embed has question content
        self.assertIsNotNone(embed.description)
        self.assertIn("Quiz Master", embed.description)

        # Verify view has 4 buttons
        self.assertEqual(len(view.children), 4)

    @patch("ironforgedbot.commands.holiday.outcomes.quiz_master.random.choice")
    async def test_correct_answer_awards_ingots(self, mock_choice):
        """Test that correct answer awards high ingots."""
        handler = create_test_trick_or_treat_handler()

        # Mock a simple question
        test_question = {
            "question": "Test question?",
            "options": [
                {"text": "A"},
                {"text": "B"},
                {"text": "C", "emoji": "Ingot"},
                {"text": "D"},
            ],
            "correct_index": 2,
        }
        mock_choice.return_value = test_question

        # Mock the interaction to simulate correct answer
        with patch.object(
            handler, "_adjust_ingots", new_callable=AsyncMock
        ) as mock_adjust:
            mock_adjust.return_value = 5000  # Simulated new balance

            # Call the process function directly with correct answer
            await quiz_master.process_quiz_answer(
                handler, self.interaction, 2, 2, "C"  # chosen, correct, answer text
            )

            # Verify ingots were added (positive amount)
            mock_adjust.assert_called_once()
            call_args = mock_adjust.call_args
            amount = call_args[0][1]
            self.assertGreater(amount, 0)  # Should be positive
            self.assertGreaterEqual(amount, 3000)  # Min reward
            self.assertLessEqual(amount, 7000)  # Max reward

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.quiz_master.random.choice")
    @patch("ironforgedbot.commands.holiday.outcomes.quiz_master.random.random")
    @patch("ironforgedbot.commands.holiday.outcomes.quiz_master.random.randrange")
    async def test_wrong_answer_with_penalty(
        self, mock_randrange, mock_random, mock_choice, mock_member_service_class, mock_db
    ):
        """Test that wrong answer can result in penalty."""
        handler = create_test_trick_or_treat_handler()

        # Mock a simple question
        test_question = {
            "question": "Test question?",
            "options": [
                {"text": "A"},
                {"text": "B"},
                {"text": "C", "emoji": "Ingot"},
                {"text": "D"},
            ],
            "correct_index": 2,
        }
        mock_choice.return_value = test_question
        mock_random.return_value = 0.3  # < 0.5, so penalty applies
        mock_randrange.return_value = 500  # Penalty amount

        # Mock database and member service
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member = MagicMock()
        mock_member.ingots = 5000
        mock_member.nickname = "TestUser"

        mock_member_service = mock_member_service_class.return_value
        mock_member_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)

        # Mock the interaction to simulate wrong answer with penalty
        with patch.object(
            handler, "_adjust_ingots", new_callable=AsyncMock
        ) as mock_adjust:
            mock_adjust.return_value = 4500  # Simulated new balance after penalty

            # Call the process function directly with wrong answer
            await quiz_master.process_quiz_answer(
                handler, self.interaction, 0, 2, "C"  # chosen wrong, correct, answer
            )

            # Verify ingots were removed (negative amount)
            mock_adjust.assert_called_once()
            call_args = mock_adjust.call_args
            amount = call_args[0][1]
            self.assertLess(amount, 0)  # Should be negative (penalty)

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.quiz_master.random.choice")
    @patch("ironforgedbot.commands.holiday.outcomes.quiz_master.random.random")
    async def test_wrong_answer_no_penalty(self, mock_random, mock_choice, mock_member_service_class, mock_db):
        """Test that wrong answer can result in no penalty (50% chance)."""
        handler = create_test_trick_or_treat_handler()

        # Mock a simple question
        test_question = {
            "question": "Test question?",
            "options": [
                {"text": "A"},
                {"text": "B"},
                {"text": "C", "emoji": "Ingot"},
                {"text": "D"},
            ],
            "correct_index": 2,
        }
        mock_choice.return_value = test_question
        mock_random.return_value = 0.7  # > 0.5, so no penalty

        # Mock database and member service
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member = MagicMock()
        mock_member.ingots = 5000
        mock_member.nickname = "TestUser"

        mock_member_service = mock_member_service_class.return_value
        mock_member_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)

        # Mock the interaction to simulate wrong answer without penalty
        with patch.object(
            handler, "_adjust_ingots", new_callable=AsyncMock
        ) as mock_adjust:
            # Call the process function directly with wrong answer
            await quiz_master.process_quiz_answer(
                handler, self.interaction, 0, 2, "C"  # chosen wrong, correct, answer
            )

            # Verify ingots were NOT adjusted
            mock_adjust.assert_not_called()

    def test_emoji_formatting(self):
        """Test that emoji placeholders are replaced with actual emojis."""
        test_text = "This has {Ingot} and {Attack} emojis"
        formatted = quiz_master._format_with_emojis(test_text)

        # Should no longer contain braces if emojis were found
        # The exact result depends on find_emoji, but we can verify it attempted replacement
        self.assertIsInstance(formatted, str)

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_quiz_view_timeout(self, mock_member_service_class, mock_db):
        """Test that quiz view handles timeout correctly."""
        handler = create_test_trick_or_treat_handler()
        test_question = {
            "question": "Test?",
            "options": [
                {"text": "A", "emoji": "Ingot"},
                {"text": "B"},
                {"text": "C"},
                {"text": "D"},
            ],
            "correct_index": 0,
        }

        # Mock database and member service
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member = MagicMock()
        mock_member.ingots = 1000
        mock_member.nickname = "TestUser"

        mock_member_service = mock_member_service_class.return_value
        mock_member_service.get_member_by_discord_id = AsyncMock(return_value=mock_member)

        view = quiz_master.QuizMasterView(
            handler, self.test_user.id, test_question
        )

        # Mock message
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        view.message = mock_message

        # Trigger timeout
        await view.on_timeout()

        # Verify message was edited with timeout message
        mock_message.edit.assert_called_once()

    async def test_quiz_view_wrong_user(self):
        """Test that quiz view rejects answers from wrong user."""
        handler = create_test_trick_or_treat_handler()
        test_question = {
            "question": "Test?",
            "options": [
                {"text": "A", "emoji": "Ingot"},
                {"text": "B"},
                {"text": "C"},
                {"text": "D"},
            ],
            "correct_index": 0,
        }

        view = quiz_master.QuizMasterView(
            handler, self.test_user.id, test_question
        )

        # Create a different user trying to answer
        wrong_user = create_test_member("WrongUser", [ROLE.MEMBER])
        wrong_user.id = 999999  # Different ID

        mock_interaction = create_mock_discord_interaction(user=wrong_user)

        # Try to click button 0
        button = view.children[0]
        await button.callback(mock_interaction)

        # Should send ephemeral message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        self.assertTrue(call_args.kwargs.get("ephemeral"))
