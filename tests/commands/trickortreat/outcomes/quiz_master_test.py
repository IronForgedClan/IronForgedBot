import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.commands.trickortreat.outcomes import quiz_master
from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    QUIZ_CORRECT_MAX,
    QUIZ_CORRECT_MIN,
    QUIZ_PENALTY_CHANCE,
)
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
        embeds = call_args.kwargs["embeds"]
        view = call_args.kwargs["view"]

        self.assertEqual(len(embeds), 2)
        intro_embed = embeds[0]
        question_embed = embeds[1]

        self.assertIsNotNone(intro_embed.description)
        self.assertIn("Quiz Master", intro_embed.description)

        self.assertIsNotNone(question_embed.description)

        self.assertEqual(len(view.children), 4)

    @patch("ironforgedbot.commands.trickortreat.outcomes.quiz_master.random.choice")
    async def test_correct_answer_awards_ingots(self, mock_choice):
        """Test that correct answer awards high ingots."""
        handler = create_test_trick_or_treat_handler()

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

        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        with patch.object(
            handler, "_adjust_ingots", new_callable=AsyncMock
        ) as mock_adjust:
            mock_adjust.return_value = 5000  # Simulated new balance

            await quiz_master.process_quiz_answer(
                handler, self.interaction, 2, 2  # chosen, correct
            )

            mock_adjust.assert_called_once()
            call_args = mock_adjust.call_args
            amount = call_args[0][1]
            self.assertGreater(amount, 0)
            self.assertGreaterEqual(amount, QUIZ_CORRECT_MIN)
            self.assertLessEqual(amount, QUIZ_CORRECT_MAX)

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.trickortreat.outcomes.quiz_master.random.choice")
    @patch("ironforgedbot.commands.trickortreat.outcomes.quiz_master.random.random")
    @patch("ironforgedbot.commands.trickortreat.outcomes.quiz_master.random.randrange")
    async def test_wrong_answer_with_penalty(
        self,
        mock_randrange,
        mock_random,
        mock_choice,
        mock_member_service_class,
        mock_db,
    ):
        """Test that wrong answer can result in penalty."""
        handler = create_test_trick_or_treat_handler()

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
        mock_random.return_value = QUIZ_PENALTY_CHANCE - 0.1
        mock_randrange.return_value = 500

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member = MagicMock()
        mock_member.ingots = 5000
        mock_member.nickname = "TestUser"

        mock_member_service = mock_member_service_class.return_value
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_member
        )

        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        with patch.object(
            handler, "_adjust_ingots", new_callable=AsyncMock
        ) as mock_adjust:
            mock_adjust.return_value = 4500  # Simulated new balance after penalty

            await quiz_master.process_quiz_answer(
                handler, self.interaction, 0, 2  # chosen wrong, correct
            )

            mock_adjust.assert_called_once()
            call_args = mock_adjust.call_args
            amount = call_args[0][1]
            self.assertLess(amount, 0)

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.trickortreat.outcomes.quiz_master.random.choice")
    @patch("ironforgedbot.commands.trickortreat.outcomes.quiz_master.random.random")
    async def test_wrong_answer_no_penalty(
        self, mock_random, mock_choice, mock_member_service_class, mock_db
    ):
        """Test that wrong answer can result in no penalty."""
        handler = create_test_trick_or_treat_handler()

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
        mock_random.return_value = QUIZ_PENALTY_CHANCE + 0.1

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member = MagicMock()
        mock_member.ingots = 5000
        mock_member.nickname = "TestUser"

        mock_member_service = mock_member_service_class.return_value
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_member
        )

        handler._get_user_info = AsyncMock(return_value=("TestUser", 5000))

        with patch.object(
            handler, "_adjust_ingots", new_callable=AsyncMock
        ) as mock_adjust:
            await quiz_master.process_quiz_answer(
                handler, self.interaction, 0, 2  # chosen wrong, correct
            )

            mock_adjust.assert_not_called()

    def test_emoji_formatting(self):
        """Test that emoji placeholders are replaced with actual emojis."""
        test_text = "This has {Ingot} and {Attack} emojis"
        formatted = quiz_master._format_with_emojis(test_text)

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

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member = MagicMock()
        mock_member.ingots = 1000
        mock_member.nickname = "TestUser"

        mock_member_service = mock_member_service_class.return_value
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_member
        )

        handler._get_user_info = AsyncMock(return_value=("TestUser", 1000))

        view = quiz_master.QuizMasterView(handler, self.test_user.id, test_question)

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        view.message = mock_message

        await view.on_timeout()

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

        view = quiz_master.QuizMasterView(handler, self.test_user.id, test_question)

        wrong_user = create_test_member("WrongUser", [ROLE.MEMBER])
        wrong_user.id = 999999  # Different ID

        mock_interaction = create_mock_discord_interaction(user=wrong_user)

        button = view.children[0]
        await button.callback(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        self.assertTrue(call_args.kwargs.get("ephemeral"))
