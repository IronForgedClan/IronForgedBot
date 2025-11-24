import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    mock_require_role,
    create_mock_discord_interaction,
    create_test_member,
)


def mock_command_price(amount: int):
    """Mock command_price decorator that just calls the wrapped function."""

    def decorator(func):
        return func

    return decorator


with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    with patch(
        "ironforgedbot.decorators.command_price.command_price", mock_command_price
    ):
        from ironforgedbot.commands.eight_ball.cmd_eight_ball import cmd_eight_ball


class TestCmdEightBall(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball._load_eight_ball_data")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.random.choice")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.asyncio.sleep")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.build_response_embed")
    async def test_cmd_eight_ball_basic(
        self, mock_build_embed, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "loading_messages": [
                {
                    "title": "Test Loading Title",
                    "description": "Test loading description",
                }
            ],
            "responses": [
                {
                    "title": "Test Response",
                    "thumbnail_url": "http://response.png",
                }
            ],
            "loading_thumbnail_url": "http://loading.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        embed = Mock()
        embed.set_thumbnail = Mock()
        embed.add_field = Mock()
        embed.set_footer = Mock()
        mock_build_embed.return_value = embed

        mock_message = Mock()
        mock_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_message

        test_question = "Will I get a drop today?"

        await cmd_eight_ball(self.mock_interaction, test_question)

        mock_load_data.assert_called_once()

        mock_sleep.assert_called_once_with(7)

        self.assertEqual(mock_build_embed.call_count, 2)

        mock_build_embed.assert_any_call(
            title="🎱 Test Loading Title",
            description="Test loading description",
            color=discord.Colour.from_rgb(255, 255, 255),
        )

        mock_build_embed.assert_any_call(
            title="Magic 8-Ball",
            description=f"{self.mock_interaction.user.display_name} asked: {test_question}\n8-ball answered: Test Response",
            color=discord.Colour.from_rgb(0, 0, 0),
        )

        self.assertEqual(embed.set_thumbnail.call_count, 2)
        embed.set_thumbnail.assert_any_call(url="http://loading.gif")
        embed.set_thumbnail.assert_any_call(url="http://response.png")

        self.mock_interaction.followup.send.assert_called_once()

        mock_message.edit.assert_called_once_with(embed=embed)

    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball._load_eight_ball_data")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.random.choice")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.asyncio.sleep")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.build_response_embed")
    async def test_cmd_eight_ball_different_question(
        self, mock_build_embed, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "loading_messages": [
                {
                    "title": "Consulting the orb...",
                    "description": "Waiting for wisdom...",
                }
            ],
            "responses": [
                {
                    "title": "Yes, definitely.",
                    "thumbnail_url": "http://8ball.png",
                }
            ],
            "loading_thumbnail_url": "http://orb.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        embed = Mock()
        embed.set_thumbnail = Mock()
        embed.add_field = Mock()
        embed.set_footer = Mock()
        mock_build_embed.return_value = embed

        mock_message = Mock()
        mock_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_message

        test_question = "Should I go to the Wilderness?"

        await cmd_eight_ball(self.mock_interaction, test_question)

        mock_build_embed.assert_any_call(
            title="Magic 8-Ball",
            description=f"{self.mock_interaction.user.display_name} asked: {test_question}\n8-ball answered: Yes, definitely.",
            color=discord.Colour.from_rgb(0, 0, 0),
        )

    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball._load_eight_ball_data")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.send_error_response")
    async def test_cmd_eight_ball_data_load_error(
        self, mock_error_response, mock_load_data
    ):
        mock_load_data.side_effect = FileNotFoundError("Data file not found")

        test_question = "Will this work?"

        await cmd_eight_ball(self.mock_interaction, test_question)

        mock_error_response.assert_called_once()
        args = mock_error_response.call_args[0]
        self.assertEqual(args[0], self.mock_interaction)
        self.assertIn("Failed to consult the Magic 8-Ball", args[1])

    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball._load_eight_ball_data")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.random.choice")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.asyncio.sleep")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.build_response_embed")
    async def test_cmd_eight_ball_multiple_responses(
        self, mock_build_embed, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "loading_messages": [
                {"title": "Loading 1", "description": "Desc 1"},
                {"title": "Loading 2", "description": "Desc 2"},
            ],
            "responses": [
                {
                    "title": "Response 1",
                    "thumbnail_url": "http://r1.png",
                },
                {
                    "title": "Response 2",
                    "thumbnail_url": "http://r2.png",
                },
                {
                    "title": "Response 3",
                    "thumbnail_url": "http://r3.png",
                },
            ],
            "loading_thumbnail_url": "http://loading.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = [
            test_data["loading_messages"][1],
            test_data["responses"][2],
        ]

        embed = Mock()
        embed.set_thumbnail = Mock()
        embed.add_field = Mock()
        embed.set_footer = Mock()
        mock_build_embed.return_value = embed

        mock_message = Mock()
        mock_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_message

        await cmd_eight_ball(self.mock_interaction, "Test question?")

        self.assertEqual(mock_choice.call_count, 2)
        mock_choice.assert_any_call(test_data["loading_messages"])
        mock_choice.assert_any_call(test_data["responses"])

        mock_build_embed.assert_any_call(
            title="🎱 Loading 2",
            description="Desc 2",
            color=discord.Colour.from_rgb(255, 255, 255),
        )

        mock_build_embed.assert_any_call(
            title="Magic 8-Ball",
            description=f"{self.mock_interaction.user.display_name} asked: Test question?\n8-ball answered: Response 3",
            color=discord.Colour.from_rgb(0, 0, 0),
        )

        embed.set_thumbnail.assert_any_call(url="http://r3.png")

    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball._load_eight_ball_data")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.random.choice")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.asyncio.sleep")
    @patch("ironforgedbot.commands.eight_ball.cmd_eight_ball.build_response_embed")
    async def test_cmd_eight_ball_long_question_truncation(
        self, mock_build_embed, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "loading_messages": [{"title": "Loading...", "description": "Thinking..."}],
            "responses": [
                {
                    "title": "Yes.",
                    "thumbnail_url": "http://8ball.png",
                }
            ],
            "loading_thumbnail_url": "http://loading.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        embed = Mock()
        embed.set_thumbnail = Mock()
        embed.add_field = Mock()
        embed.set_footer = Mock()
        mock_build_embed.return_value = embed

        mock_message = Mock()
        mock_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_message

        very_long_question = "A" * 5000  # Intentionally too long

        await cmd_eight_ball(self.mock_interaction, very_long_question)

        MAX_DESCRIPTION_LENGTH = 4096
        display_name = self.mock_interaction.user.display_name
        response_title = "Yes."
        format_overhead = (
            len(display_name)
            + len(" asked: ")
            + len("\n8-ball answered: ")
            + len(response_title)
        )
        max_question_length = MAX_DESCRIPTION_LENGTH - format_overhead - 10
        expected_truncated = very_long_question[:max_question_length] + "..."

        mock_build_embed.assert_any_call(
            title="Magic 8-Ball",
            description=f"{display_name} asked: {expected_truncated}\n8-ball answered: {response_title}",
            color=discord.Colour.from_rgb(0, 0, 0),
        )

        actual_call = [
            call
            for call in mock_build_embed.call_args_list
            if "Magic 8-Ball" in str(call) and "8-ball answered" in str(call)
        ][0]
        actual_description = actual_call[1]["description"]
        self.assertLessEqual(len(actual_description), MAX_DESCRIPTION_LENGTH)
