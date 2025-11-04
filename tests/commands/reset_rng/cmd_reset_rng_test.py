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
    with patch("ironforgedbot.decorators.command_price.command_price", mock_command_price):
        from ironforgedbot.commands.reset_rng.cmd_reset_rng import cmd_reset_rng


class TestCmdResetRng(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.discord.Embed")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_success(
        self, mock_build_embed, mock_discord_embed, mock_random, mock_sleep
    ):
        mock_random.return_value = 0.3

        dice_embed = Mock()
        dice_embed.set_image = Mock()
        mock_discord_embed.return_value = dice_embed

        result_embed = Mock()
        result_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = result_embed

        mock_dice_message = Mock()
        mock_dice_message.delete = AsyncMock()

        # First send() for dice embed, second for result embed
        self.mock_interaction.followup.send.side_effect = [
            mock_dice_message,
            Mock(),
        ]

        await cmd_reset_rng(self.mock_interaction)

        # Verify dice embed created with correct description and color
        mock_discord_embed.assert_called_once_with(
            description=f"### {self.mock_interaction.user.mention} is rolling for an RNG reset...",
            color=discord.Colour.blurple()
        )
        dice_embed.set_image.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Dice_(6).png/245px-Dice_(6).png"
        )
        self.mock_interaction.followup.send.assert_any_call(embed=dice_embed)

        # Verify 5 second sleep
        mock_sleep.assert_called_once_with(5)

        # Verify dice message deleted
        mock_dice_message.delete.assert_called_once()

        # Verify result embed built and sent
        mock_build_embed.assert_called_once_with(
            title="RNG Reset Successful!",
            description="Your RNG has been restored. That pet is definitely dropping on your next kill. Probably.",
            color=discord.Colour.green(),
        )
        result_embed.set_thumbnail.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Reward_casket_%28master%29.png/150px-Reward_casket_%28master%29.png"
        )
        self.mock_interaction.followup.send.assert_any_call(embed=result_embed)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.discord.Embed")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_failure(
        self, mock_build_embed, mock_discord_embed, mock_random, mock_sleep
    ):
        mock_random.return_value = 0.7

        dice_embed = Mock()
        dice_embed.set_image = Mock()
        mock_discord_embed.return_value = dice_embed

        result_embed = Mock()
        result_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = result_embed

        mock_dice_message = Mock()
        mock_dice_message.delete = AsyncMock()

        # First send() for dice embed, second for result embed
        self.mock_interaction.followup.send.side_effect = [
            mock_dice_message,
            Mock(),
        ]

        await cmd_reset_rng(self.mock_interaction)

        # Verify dice embed created with correct description and color
        mock_discord_embed.assert_called_once_with(
            description=f"### {self.mock_interaction.user.mention} is rolling for an RNG reset...",
            color=discord.Colour.blurple()
        )
        dice_embed.set_image.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Dice_(6).png/245px-Dice_(6).png"
        )
        self.mock_interaction.followup.send.assert_any_call(embed=dice_embed)

        # Verify 5 second sleep
        mock_sleep.assert_called_once_with(5)

        # Verify dice message deleted
        mock_dice_message.delete.assert_called_once()

        # Verify result embed built and sent
        mock_build_embed.assert_called_once_with(
            title="You rolled a 0!",
            description="The RNG gods have denied your request. Enjoy staying dry for another 10,000 kills.",
            color=discord.Colour.red(),
        )
        result_embed.set_thumbnail.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Skull.png/130px-Skull.png"
        )
        self.mock_interaction.followup.send.assert_any_call(embed=result_embed)

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.discord.Embed")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_boundary_success(
        self, mock_build_embed, mock_discord_embed, mock_random, mock_sleep
    ):
        mock_random.return_value = 0.49999

        dice_embed = Mock()
        dice_embed.set_image = Mock()
        mock_discord_embed.return_value = dice_embed

        result_embed = Mock()
        result_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = result_embed

        mock_dice_message = Mock()
        mock_dice_message.delete = AsyncMock()

        # First send() for dice embed, second for result embed
        self.mock_interaction.followup.send.side_effect = [
            mock_dice_message,
            Mock(),
        ]

        await cmd_reset_rng(self.mock_interaction)

        # Verify dice embed created with correct description and color
        mock_discord_embed.assert_called_once_with(
            description=f"### {self.mock_interaction.user.mention} is rolling for an RNG reset...",
            color=discord.Colour.blurple()
        )
        dice_embed.set_image.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Dice_(6).png/245px-Dice_(6).png"
        )
        self.mock_interaction.followup.send.assert_any_call(embed=dice_embed)

        # Verify 5 second sleep
        mock_sleep.assert_called_once_with(5)

        # Verify dice message deleted
        mock_dice_message.delete.assert_called_once()

        # Verify result embed built and sent (boundary case should succeed)
        mock_build_embed.assert_called_once_with(
            title="RNG Reset Successful!",
            description="Your RNG has been restored. That pet is definitely dropping on your next kill. Probably.",
            color=discord.Colour.green(),
        )

    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.asyncio.sleep")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.random.random")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.discord.Embed")
    @patch("ironforgedbot.commands.reset_rng.cmd_reset_rng.build_response_embed")
    async def test_cmd_reset_rng_boundary_failure(
        self, mock_build_embed, mock_discord_embed, mock_random, mock_sleep
    ):
        mock_random.return_value = 0.5

        dice_embed = Mock()
        dice_embed.set_image = Mock()
        mock_discord_embed.return_value = dice_embed

        result_embed = Mock()
        result_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = result_embed

        mock_dice_message = Mock()
        mock_dice_message.delete = AsyncMock()

        # First send() for dice embed, second for result embed
        self.mock_interaction.followup.send.side_effect = [
            mock_dice_message,
            Mock(),
        ]

        await cmd_reset_rng(self.mock_interaction)

        # Verify dice embed created with correct description and color
        mock_discord_embed.assert_called_once_with(
            description=f"### {self.mock_interaction.user.mention} is rolling for an RNG reset...",
            color=discord.Colour.blurple()
        )
        dice_embed.set_image.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Dice_(6).png/245px-Dice_(6).png"
        )
        self.mock_interaction.followup.send.assert_any_call(embed=dice_embed)

        # Verify 5 second sleep
        mock_sleep.assert_called_once_with(5)

        # Verify dice message deleted
        mock_dice_message.delete.assert_called_once()

        # Verify result embed built and sent (boundary case should fail)
        mock_build_embed.assert_called_once_with(
            title="You rolled a 0!",
            description="The RNG gods have denied your request. Enjoy staying dry for another 10,000 kills.",
            color=discord.Colour.red(),
        )
