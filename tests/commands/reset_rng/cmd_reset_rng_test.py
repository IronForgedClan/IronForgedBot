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
        from ironforgedbot.commands.reset_rng.cmd_reset_rng import cmd_reset_rng


class TestCmdResetRng(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng._load_reset_rng_data")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.choice")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_success(
        self, mock_build_embed, mock_random, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "dice_rolling": [
                {"title": "Test Dice Title", "description": "Test dice description"}
            ],
            "success": [
                {
                    "title": "Test Success",
                    "description": "Test success desc",
                    "thumbnail_url": "http://success.png",
                }
            ],
            "failure": [
                {
                    "title": "Test Failure",
                    "description": "Test failure desc",
                    "thumbnail_url": "http://failure.png",
                }
            ],
            "dice_thumbnail_url": "http://dice.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        mock_random.return_value = 0.3

        embed = Mock()
        embed.set_thumbnail = Mock()
        mock_build_embed.return_value = embed

        mock_dice_message = Mock()
        mock_dice_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_dice_message

        await cmd_reset_rng(self.mock_interaction)

        mock_load_data.assert_called_once()

        mock_sleep.assert_called_once_with(7)

        self.assertEqual(mock_build_embed.call_count, 2)

        mock_build_embed.assert_any_call(
            title="Test Dice Title",
            description="Test dice description",
            color=discord.Colour.blurple(),
        )

        mock_build_embed.assert_any_call(
            title="Test Success",
            description="Test success desc",
            color=discord.Colour.green(),
        )

        self.assertEqual(embed.set_thumbnail.call_count, 2)

        self.mock_interaction.followup.send.assert_called_once()
        mock_dice_message.edit.assert_called_once_with(embed=embed)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng._load_reset_rng_data")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.choice")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_failure(
        self, mock_build_embed, mock_random, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "dice_rolling": [
                {"title": "Test Dice Title", "description": "Test dice description"}
            ],
            "success": [
                {
                    "title": "Test Success",
                    "description": "Test success desc",
                    "thumbnail_url": "http://success.png",
                }
            ],
            "failure": [
                {
                    "title": "Test Failure",
                    "description": "Test failure desc",
                    "thumbnail_url": "http://failure.png",
                }
            ],
            "dice_thumbnail_url": "http://dice.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        mock_random.return_value = 0.7

        embed = Mock()
        embed.set_thumbnail = Mock()
        mock_build_embed.return_value = embed

        mock_dice_message = Mock()
        mock_dice_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_dice_message

        await cmd_reset_rng(self.mock_interaction)

        mock_load_data.assert_called_once()

        mock_sleep.assert_called_once_with(7)

        self.assertEqual(mock_build_embed.call_count, 2)

        mock_build_embed.assert_any_call(
            title="Test Dice Title",
            description="Test dice description",
            color=discord.Colour.blurple(),
        )

        mock_build_embed.assert_any_call(
            title="Test Failure",
            description="Test failure desc",
            color=discord.Colour.red(),
        )

        self.assertEqual(embed.set_thumbnail.call_count, 2)

        self.mock_interaction.followup.send.assert_called_once()
        mock_dice_message.edit.assert_called_once_with(embed=embed)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng._load_reset_rng_data")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.choice")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_boundary_success(
        self, mock_build_embed, mock_random, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "dice_rolling": [{"title": "", "description": "Rolling..."}],
            "success": [
                {
                    "title": "Success!",
                    "description": "You won!",
                    "thumbnail_url": "http://success.png",
                }
            ],
            "failure": [
                {
                    "title": "Failure!",
                    "description": "You lost!",
                    "thumbnail_url": "http://failure.png",
                }
            ],
            "dice_thumbnail_url": "http://dice.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        mock_random.return_value = 0.49999

        embed = Mock()
        embed.set_thumbnail = Mock()
        mock_build_embed.return_value = embed

        mock_dice_message = Mock()
        mock_dice_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_dice_message

        await cmd_reset_rng(self.mock_interaction)

        mock_load_data.assert_called_once()

        mock_sleep.assert_called_once_with(7)

        mock_build_embed.assert_any_call(
            title="Success!",
            description="You won!",
            color=discord.Colour.green(),
        )

        self.mock_interaction.followup.send.assert_called_once()
        mock_dice_message.edit.assert_called_once_with(embed=embed)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng._load_reset_rng_data")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.choice")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_boundary_failure(
        self, mock_build_embed, mock_random, mock_sleep, mock_choice, mock_load_data
    ):
        test_data = {
            "dice_rolling": [{"title": "", "description": "Rolling..."}],
            "success": [
                {
                    "title": "Success!",
                    "description": "You won!",
                    "thumbnail_url": "http://success.png",
                }
            ],
            "failure": [
                {
                    "title": "Failure!",
                    "description": "You lost!",
                    "thumbnail_url": "http://failure.png",
                }
            ],
            "dice_thumbnail_url": "http://dice.gif",
        }
        mock_load_data.return_value = test_data

        mock_choice.side_effect = lambda x: x[0]

        mock_random.return_value = 0.5

        embed = Mock()
        embed.set_thumbnail = Mock()
        mock_build_embed.return_value = embed

        mock_dice_message = Mock()
        mock_dice_message.edit = AsyncMock()

        self.mock_interaction.followup.send.return_value = mock_dice_message

        await cmd_reset_rng(self.mock_interaction)

        mock_load_data.assert_called_once()

        mock_sleep.assert_called_once_with(7)

        mock_build_embed.assert_any_call(
            title="Failure!",
            description="You lost!",
            color=discord.Colour.red(),
        )

        self.mock_interaction.followup.send.assert_called_once()
        mock_dice_message.edit.assert_called_once_with(embed=embed)
