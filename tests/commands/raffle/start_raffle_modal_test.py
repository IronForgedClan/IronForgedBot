import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.raffle.start_raffle_modal import StartRaffleModal
from tests.helpers import create_mock_discord_interaction


class TestStartRaffleModal(unittest.IsolatedAsyncioTestCase):
    async def test_modal_creates(self):
        modal = StartRaffleModal()

        self.assertEqual(modal.title, "Start Raffle")
        self.assertEqual(len(modal.children), 1)

        self.assertEqual(modal.ticket_price.label, "Price per ticket")
        self.assertEqual(modal.ticket_price.placeholder, "5000")
        self.assertEqual(modal.ticket_price.required, True)

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_success(self, mock_state):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}

        modal = StartRaffleModal()
        modal.ticket_price._value = "5000"

        interaction = create_mock_discord_interaction()
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)
        interaction.followup.send.assert_called_once_with(
            "##  Raffle Started\nTicket Price:  **5,000**\n\n"
            "- Members can now buy raffle tickets with the `/raffle` command.\n"
            "- Admins can now end the raffle and select a winner by running the "
            "`/raffle` command and clicking the red 'End Raffle' button."
        )

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_fail_invalid_price(
        self, mock_state, mock_send_error_response
    ):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}

        modal = StartRaffleModal()
        modal.ticket_price._value = "test"

        interaction = create_mock_discord_interaction()
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)
        mock_send_error_response.assert_awaited_with(
            interaction,
            "**test** is an invalid ticket price.",
        )

    @patch("ironforgedbot.commands.raffle.start_raffle_modal.send_error_response")
    @patch("ironforgedbot.commands.raffle.start_raffle_modal.STATE")
    async def test_modal_submission_fail_negative_price(
        self, mock_state, mock_send_error_response
    ):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}

        modal = StartRaffleModal()
        modal.ticket_price._value = "-10"

        interaction = create_mock_discord_interaction()
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)
        mock_send_error_response.assert_awaited_with(
            interaction,
            "**-10** is an invalid ticket price.",
        )
