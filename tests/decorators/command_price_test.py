import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE


class TestCommandPriceDecorator(unittest.IsolatedAsyncioTestCase):
    @patch(
        "ironforgedbot.decorators.views.command_price_confirmation_view.CommandPriceConfirmationView"
    )
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.helpers.find_emoji")
    async def test_command_price_shows_confirmation_embed(
        self, mock_find_emoji, mock_build_embed, mock_view_class
    ):
        """Test that command_price decorator shows confirmation embed via channel.send."""
        from ironforgedbot.decorators.command_price import command_price

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed
        mock_view = Mock()
        mock_view_class.return_value = mock_view

        mock_message = AsyncMock()

        @command_price(100)
        async def test_command(interaction):
            pass

        mock_user = Mock()
        mock_user.id = 12345
        mock_user.mention = "<@12345>"

        mock_original_message = Mock(spec=discord.Message)

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=mock_message)

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.user = mock_user
        mock_interaction.channel = mock_channel
        mock_interaction.original_response = AsyncMock(return_value=mock_original_message)

        await test_command(mock_interaction)

        mock_find_emoji.assert_called_once_with("Ingot")
        mock_build_embed.assert_called_once_with(
            title=f"<:Ingot:123> Command Price",
            description="This command costs <:Ingot:123> **100** ingots to use.\n\nDo you want to continue?",
            color=discord.Colour.gold(),
        )
        mock_interaction.original_response.assert_called_once()
        mock_channel.send.assert_called_once_with(
            content="<@12345>",
            embed=mock_embed,
            view=mock_view,
            reference=mock_original_message,
        )

    @patch(
        "ironforgedbot.decorators.views.command_price_confirmation_view.CommandPriceConfirmationView"
    )
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.helpers.find_emoji")
    async def test_command_price_creates_view_with_correct_parameters(
        self, mock_find_emoji, mock_build_embed, mock_view_class
    ):
        """Test that command_price creates CommandPriceConfirmationView with correct parameters."""
        from ironforgedbot.decorators.command_price import command_price

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed
        mock_view = Mock()
        mock_view_class.return_value = mock_view

        mock_message = AsyncMock()

        @command_price(250)
        async def my_expensive_command(interaction):
            pass

        mock_user = Mock()
        mock_user.id = 12345
        mock_user.mention = "<@12345>"

        mock_original_message = Mock(spec=discord.Message)

        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock(return_value=mock_message)

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.user = mock_user
        mock_interaction.channel = mock_channel
        mock_interaction.original_response = AsyncMock(return_value=mock_original_message)

        await my_expensive_command(mock_interaction)

        call_kwargs = mock_view_class.call_args[1]
        self.assertEqual(call_kwargs["cost"], 250)
        self.assertEqual(call_kwargs["command_name"], "my_expensive_command")
        self.assertEqual(call_kwargs["original_args"], (mock_interaction,))
        self.assertEqual(call_kwargs["original_kwargs"], {})
        self.assertEqual(call_kwargs["user_id"], 12345)
        self.assertEqual(mock_view.confirmation_message, mock_message)

    async def test_command_price_raises_error_for_non_interaction(self):
        """Test that command_price raises error if first argument is not an Interaction."""
        from ironforgedbot.decorators.command_price import command_price

        @command_price(100)
        async def test_command(interaction):
            pass

        with self.assertRaises(ReferenceError) as context:
            await test_command("not an interaction")

        self.assertIn("Expected discord.Interaction", str(context.exception))
