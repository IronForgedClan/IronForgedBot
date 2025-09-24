import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.commands.raffle.start_raffle_modal import StartRaffleModal


class TestStartRaffleModal(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.response.send_message = AsyncMock()
        self.mock_interaction.response.defer = AsyncMock()

    async def test_modal_creates(self):
        modal = StartRaffleModal()

        self.assertEqual(modal.title, "Start Raffle")
        self.assertEqual(len(modal.children), 1)

        self.assertEqual(modal.ticket_price.placeholder, "5000")
        self.assertEqual(modal.ticket_price.required, True)

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.find_emoji")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_success(self, mock_state, mock_find_emoji):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}
        mock_find_emoji.side_effect = lambda name: (
            "🎫" if name == "Raffle_Ticket" else "💰"
        )

        modal = StartRaffleModal()
        modal.ticket_price._value = "5000"

        await modal.on_submit(self.mock_interaction)

        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)
        self.mock_interaction.response.send_message.assert_called_once_with(
            "## 🎫 Raffle Started\nTicket Price: 💰 **5,000**\n\n"
            "- Members can now buy raffle tickets with the `raffle` command.\n"
            "- Admins can now end the raffle and select a winner by running the "
            "`raffle` command and clicking the red 'End Raffle' button."
        )

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.find_emoji")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_fail_invalid_price(
        self, mock_state, mock_find_emoji, mock_send_error_response
    ):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}
        mock_find_emoji.side_effect = lambda name: (
            "🎫" if name == "Raffle_Ticket" else "💰"
        )

        modal = StartRaffleModal()
        modal.ticket_price._value = "test"

        await modal.on_submit(self.mock_interaction)

        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "💰 **test** is an invalid 🎫 ticket price.", report_to_channel=False
        )

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.find_emoji")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_fail_negative_price(
        self, mock_state, mock_find_emoji, mock_send_error_response
    ):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}
        mock_find_emoji.side_effect = lambda name: (
            "🎫" if name == "Raffle_Ticket" else "💰"
        )

        modal = StartRaffleModal()
        modal.ticket_price._value = "-10"

        await modal.on_submit(self.mock_interaction)

        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "💰 **-10** is an invalid 🎫 ticket price.", report_to_channel=False
        )

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.find_emoji")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_fail_zero_price(
        self, mock_state, mock_find_emoji, mock_send_error_response
    ):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}
        mock_find_emoji.side_effect = lambda name: (
            "🎫" if name == "Raffle_Ticket" else "💰"
        )

        modal = StartRaffleModal()
        modal.ticket_price._value = "0"

        await modal.on_submit(self.mock_interaction)

        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)
        self.mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "💰 **0** is an invalid 🎫 ticket price.", report_to_channel=False
        )
