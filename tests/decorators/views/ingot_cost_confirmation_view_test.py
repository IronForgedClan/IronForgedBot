import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.decorators.views.ingot_cost_confirmation_view import (
    IngotCostConfirmationView,
)
from ironforgedbot.services.ingot_service import IngotServiceResponse


class TestIngotCostConfirmationView(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_wrapped_function = AsyncMock()
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.user = Mock()
        self.mock_interaction.user.id = 12345
        self.mock_interaction.delete_original_response = AsyncMock()
        self.mock_interaction.edit_original_response = AsyncMock()

        self.view = IngotCostConfirmationView(
            cost=100,
            wrapped_function=self.mock_wrapped_function,
            original_args=(self.mock_interaction,),
            original_kwargs={},
            command_name="test_command",
        )

    @patch("ironforgedbot.decorators.views.ingot_cost_confirmation_view.find_emoji")
    @patch(
        "ironforgedbot.decorators.views.ingot_cost_confirmation_view.build_response_embed"
    )
    @patch("ironforgedbot.decorators.views.ingot_cost_confirmation_view.db")
    @patch("ironforgedbot.decorators.views.ingot_cost_confirmation_view.IngotService")
    async def test_on_confirm_with_sufficient_ingots(
        self, mock_ingot_service_class, mock_db, mock_build_embed, mock_find_emoji
    ):
        """Test confirm button with sufficient ingots edits to show success and executes the wrapped function."""
        mock_button_interaction = AsyncMock(spec=discord.Interaction)
        mock_button_interaction.user.id = 12345
        mock_button_interaction.response.defer = AsyncMock()

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_ingot_service = AsyncMock()
        mock_ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            status=True, message="Success", new_total=50
        )
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        await self.view.on_confirm(mock_button_interaction)

        mock_button_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            12345, -100, None, "Command usage: test_command"
        )

        # Verify buttons are removed
        self.assertEqual(len(self.view.children), 0)

        # Verify success embed is built
        mock_build_embed.assert_called_once_with(
            title="✅ Ingots Deducted",
            description="Deducted <:Ingot:123> **100** ingots\nNew balance: <:Ingot:123> **50**",
            color=discord.Colour.green(),
        )

        # Verify original message is edited (not deleted)
        self.mock_interaction.edit_original_response.assert_called_once_with(
            embed=mock_embed, view=self.view
        )

        self.mock_wrapped_function.assert_called_once_with(mock_button_interaction)

    @patch("ironforgedbot.decorators.views.ingot_cost_confirmation_view.find_emoji")
    @patch(
        "ironforgedbot.decorators.views.ingot_cost_confirmation_view.build_response_embed"
    )
    @patch("ironforgedbot.decorators.views.ingot_cost_confirmation_view.db")
    @patch("ironforgedbot.decorators.views.ingot_cost_confirmation_view.IngotService")
    async def test_on_confirm_with_insufficient_ingots(
        self,
        mock_ingot_service_class,
        mock_db,
        mock_build_embed,
        mock_find_emoji,
    ):
        """Test confirm button with insufficient ingots edits to show error message."""
        mock_button_interaction = AsyncMock(spec=discord.Interaction)
        mock_button_interaction.user.id = 12345
        mock_button_interaction.response.defer = AsyncMock()

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_ingot_service = AsyncMock()
        mock_ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            status=False, message="Insufficient ingots", new_total=25
        )
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_find_emoji.return_value = "<:Ingot:123>"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        await self.view.on_confirm(mock_button_interaction)

        mock_button_interaction.response.defer.assert_called_once_with(ephemeral=True)
        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            12345, -100, None, "Command usage: test_command"
        )

        # Verify buttons are removed
        self.assertEqual(len(self.view.children), 0)

        # Verify error embed is built
        mock_build_embed.assert_called_once_with(
            title="❌ Insufficient Ingots",
            description="You need <:Ingot:123> **100** but only have <:Ingot:123> **25**",
            color=discord.Colour.red(),
        )

        # Verify original message is edited (not deleted)
        self.mock_interaction.edit_original_response.assert_called_once_with(
            embed=mock_embed, view=self.view
        )

        self.mock_wrapped_function.assert_not_called()

    async def test_on_cancel(self):
        """Test cancel button deletes the message without any additional response."""
        mock_button_interaction = AsyncMock(spec=discord.Interaction)
        mock_button_interaction.response.defer = AsyncMock()

        await self.view.on_cancel(mock_button_interaction)

        mock_button_interaction.response.defer.assert_called_once_with(ephemeral=True)
        self.mock_interaction.delete_original_response.assert_called_once()
        self.mock_wrapped_function.assert_not_called()

    async def test_on_timeout_disables_buttons(self):
        """Test timeout disables all buttons in the view."""
        self.assertEqual(len(self.view.children), 2)
        for item in self.view.children:
            self.assertFalse(item.disabled)

        await self.view.on_timeout()

        for item in self.view.children:
            self.assertTrue(item.disabled)
