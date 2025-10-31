import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE


class TestCostIngotsDecorator(unittest.IsolatedAsyncioTestCase):
    @patch(
        "ironforgedbot.decorators.views.ingot_cost_confirmation_view.IngotCostConfirmationView"
    )
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.helpers.find_emoji")
    async def test_cost_ingots_shows_confirmation_embed(
        self, mock_find_emoji, mock_build_embed, mock_view_class
    ):
        """Test that cost_ingots decorator shows confirmation embed."""
        from ironforgedbot.decorators.cost_ingots import cost_ingots

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed
        mock_view = Mock()
        mock_view_class.return_value = mock_view

        @cost_ingots(100)
        async def test_command(interaction):
            pass

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.response.send_message = AsyncMock()

        await test_command(mock_interaction)

        mock_find_emoji.assert_called_once_with("Ingot")
        mock_build_embed.assert_called_once_with(
            title="💰 Command Cost",
            description="This command costs <:Ingot:123> **100** ingots to use.\n\nDo you want to continue?",
            color=discord.Colour.gold(),
        )
        mock_view_class.assert_called_once()
        mock_interaction.response.send_message.assert_called_once_with(
            embed=mock_embed, view=mock_view, ephemeral=True
        )

    @patch(
        "ironforgedbot.decorators.views.ingot_cost_confirmation_view.IngotCostConfirmationView"
    )
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.helpers.find_emoji")
    async def test_cost_ingots_with_non_ephemeral(
        self, mock_find_emoji, mock_build_embed, mock_view_class
    ):
        """Test that cost_ingots decorator respects ephemeral parameter."""
        from ironforgedbot.decorators.cost_ingots import cost_ingots

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed
        mock_view = Mock()
        mock_view_class.return_value = mock_view

        @cost_ingots(100, ephemeral=False)
        async def test_command(interaction):
            pass

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.response.send_message = AsyncMock()

        await test_command(mock_interaction)

        mock_interaction.response.send_message.assert_called_once_with(
            embed=mock_embed, view=mock_view, ephemeral=False
        )

    @patch(
        "ironforgedbot.decorators.views.ingot_cost_confirmation_view.IngotCostConfirmationView"
    )
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.helpers.find_emoji")
    async def test_cost_ingots_creates_view_with_correct_parameters(
        self, mock_find_emoji, mock_build_embed, mock_view_class
    ):
        """Test that cost_ingots creates IngotCostConfirmationView with correct parameters."""
        from ironforgedbot.decorators.cost_ingots import cost_ingots

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed
        mock_view = Mock()
        mock_view_class.return_value = mock_view

        @cost_ingots(250)
        async def my_expensive_command(interaction):
            pass

        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.response.send_message = AsyncMock()

        await my_expensive_command(mock_interaction)

        call_kwargs = mock_view_class.call_args[1]
        self.assertEqual(call_kwargs["cost"], 250)
        self.assertEqual(call_kwargs["command_name"], "my_expensive_command")
        self.assertEqual(call_kwargs["original_args"], (mock_interaction,))
        self.assertEqual(call_kwargs["original_kwargs"], {})

    async def test_cost_ingots_raises_error_for_non_interaction(self):
        """Test that cost_ingots raises error if first argument is not an Interaction."""
        from ironforgedbot.decorators.cost_ingots import cost_ingots

        @cost_ingots(100)
        async def test_command(interaction):
            pass

        with self.assertRaises(ReferenceError) as context:
            await test_command("not an interaction")

        self.assertIn("Expected discord.Interaction", str(context.exception))
