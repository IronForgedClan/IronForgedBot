import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.commands.raffle.buy_ticket_modal import BuyTicketModal


class TestBuyTicketModal(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.user = Mock()
        self.mock_interaction.user.id = 12345
        self.mock_interaction.user.display_name = "TestUser"
        self.mock_interaction.followup.send = AsyncMock()
        self.mock_interaction.response.defer = AsyncMock()
        self.mock_interaction.response.send_message = AsyncMock()

    async def test_modal_creates(self):
        modal = BuyTicketModal()

        self.assertEqual(modal.title, "Buy Raffle Tickets")
        self.assertEqual(len(modal.children), 1)

        self.assertEqual(modal.ticket_qty.placeholder, "10")
        self.assertEqual(modal.ticket_qty.max_length, 10)
        self.assertEqual(modal.ticket_qty.required, True)

    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.normalize_discord_string")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.find_emoji")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.build_response_embed")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.db")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.RaffleService")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.STATE")
    async def test_modal_submission_success(
        self,
        mock_state,
        mock_raffle_service_class,
        mock_db,
        mock_build_embed,
        mock_find_emoji,
        mock_normalize,
    ):
        mock_state.state = {"raffle_price": 5000}
        mock_find_emoji.side_effect = lambda name: (
            "🎫" if name == "Raffle_Ticket" else "💰"
        )
        mock_normalize.return_value = "TestUser"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.status = True

        mock_raffle_service = AsyncMock()
        mock_raffle_service.try_buy_ticket.return_value = mock_result
        mock_raffle_service_class.return_value = mock_raffle_service

        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        modal = BuyTicketModal()
        modal.ticket_qty._value = "5"

        await modal.on_submit(self.mock_interaction)

        mock_raffle_service.try_buy_ticket.assert_called_once_with(12345, 5000, 5)

        mock_build_embed.assert_called_once_with(
            title="🎫 Ticket Purchase",
            description="**TestUser** just bought 🎫 **5** raffle tickets for 💰 **25,000**.",
            color=modal.ticket_embed_color,
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.normalize_discord_string")
    async def test_modal_submission_invalid_quantity(
        self, mock_normalize, mock_send_error
    ):
        mock_normalize.return_value = "TestUser"

        modal = BuyTicketModal()
        modal.ticket_qty._value = "abc"

        await modal.on_submit(self.mock_interaction)

        mock_send_error.assert_called_once_with(
            self.mock_interaction,
            "**TestUser** tried to buy an invalid quantity of tickets.",
        )

    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.normalize_discord_string")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.find_emoji")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.build_response_embed")
    async def test_modal_submission_negative_quantity(
        self, mock_build_embed, mock_find_emoji, mock_normalize
    ):
        mock_normalize.return_value = "TestUser"
        mock_find_emoji.return_value = "🎫"

        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        modal = BuyTicketModal()
        modal.ticket_qty._value = "-5"

        await modal.on_submit(self.mock_interaction)

        mock_build_embed.assert_called_once_with(
            title="🎫 Ticket Purchase",
            description="**TestUser** just tried to buy 🎫 **-5** raffle tickets. What a joker.",
            color=modal.ticket_embed_color,
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.normalize_discord_string")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.db")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.RaffleService")
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.STATE")
    async def test_modal_submission_insufficient_funds(
        self,
        mock_state,
        mock_raffle_service_class,
        mock_db,
        mock_normalize,
        mock_send_error,
    ):
        mock_state.state = {"raffle_price": 5000}
        mock_normalize.return_value = "TestUser"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.status = False
        mock_result.message = "Insufficient ingots"

        mock_raffle_service = AsyncMock()
        mock_raffle_service.try_buy_ticket.return_value = mock_result
        mock_raffle_service_class.return_value = mock_raffle_service

        modal = BuyTicketModal()
        modal.ticket_qty._value = "10"

        await modal.on_submit(self.mock_interaction)

        mock_send_error.assert_called_once_with(
            self.mock_interaction, "Insufficient ingots"
        )
