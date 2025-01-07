import unittest
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.commands.raffle.buy_ticket_modal import BuyTicketModal
from ironforgedbot.storage.types import Member
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestBuyTicketModal(unittest.IsolatedAsyncioTestCase):
    async def test_modal_creates(self):
        modal = BuyTicketModal()

        self.assertEqual(modal.title, "Buy Raffle Tickets")
        self.assertEqual(len(modal.children), 1)

        self.assertEqual(modal.ticket_qty.label, "How many tickets?")
        self.assertEqual(modal.ticket_qty.placeholder, "10")
        self.assertEqual(modal.ticket_qty.max_length, 10)
        self.assertEqual(modal.ticket_qty.required, True)

    @patch(
        "ironforgedbot.commands.raffle.buy_ticket_modal.STORAGE", new_callable=AsyncMock
    )
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.STATE")
    async def test_modal_submission_success(self, mock_state, mock_storage):
        caller = create_test_member("tester", [])
        mock_state.state = {"raffle_price": 5000}

        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=caller.display_name, ingots=30000
        )

        modal = BuyTicketModal()
        modal.ticket_qty._value = "5"

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        interaction.followup.send.assert_called_once()

        expected_title = " Ticket Purchase"
        expected_description = (
            "**tester** just bought  **5** raffle tickets for  **25,000**."
        )

        _, kwargs = interaction.followup.send.call_args
        actual_embed = kwargs.get("embed")

        assert actual_embed
        self.assertIsInstance(actual_embed, discord.Embed)
        self.assertEqual(actual_embed.title, expected_title)
        self.assertEqual(actual_embed.description, expected_description)

        mock_storage.update_members.assert_called_with(
            [Member(id=12345, runescape_name="tester", ingots=5000)],
            "tester",
            note="Pay for 5 raffle tickets",
        )
        mock_storage.add_raffle_tickets.assert_called_with(12345, 5)

    @patch(
        "ironforgedbot.commands.raffle.buy_ticket_modal.STORAGE", new_callable=AsyncMock
    )
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.send_error_response")
    async def test_modal_submission_fail_invalid_quantity(
        self, mock_send_error_response, mock_storage
    ):
        caller = create_test_member("tester", [])
        modal = BuyTicketModal()
        modal.ticket_qty._value = "test"

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        mock_send_error_response.assert_awaited_with(
            interaction, "**tester** tried to buy an invalid quantity of tickets."
        )

        mock_storage.update_members.assert_not_called()
        mock_storage.add_raffle_tickets.assert_not_called()

    async def test_modal_submission_fail_invalid_number(self):
        caller = create_test_member("tester", [])
        modal = BuyTicketModal()
        modal.ticket_qty._value = "-5"

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        interaction.followup.send.assert_called_once()

        expected_title = " Ticket Purchase"
        expected_description = (
            "**tester** just tried to buy  **-5** raffle tickets. What a joker."
        )

        _, kwargs = interaction.followup.send.call_args
        actual_embed = kwargs.get("embed")

        assert actual_embed
        self.assertIsInstance(actual_embed, discord.Embed)
        self.assertEqual(actual_embed.title, expected_title)
        self.assertEqual(actual_embed.description, expected_description)

    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.send_error_response")
    @patch(
        "ironforgedbot.commands.raffle.buy_ticket_modal.STORAGE", new_callable=AsyncMock
    )
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.STATE")
    async def test_modal_submission_fail_member_not_found(
        self, mock_state, mock_storage, mock_send_error_response
    ):
        caller = create_test_member("tester", [])
        mock_state.state = {"raffle_price": 5000}

        mock_storage.read_member.return_value = None

        modal = BuyTicketModal()
        modal.ticket_qty._value = "5"

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        mock_send_error_response.assert_awaited_with(
            interaction,
            "**tester** not found in storage, please reach out to leadership.",
        )
        mock_storage.update_members.assert_not_called()
        mock_storage.add_raffle_tickets.assert_not_called()

    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.send_error_response")
    @patch(
        "ironforgedbot.commands.raffle.buy_ticket_modal.STORAGE", new_callable=AsyncMock
    )
    @patch("ironforgedbot.commands.raffle.buy_ticket_modal.STATE")
    async def test_modal_submission_fail_insufficient_funds(
        self, mock_state, mock_storage, mock_send_error_response
    ):
        caller = create_test_member("tester", [])
        mock_state.state = {"raffle_price": 5000}

        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=caller.display_name, ingots=20000
        )

        modal = BuyTicketModal()
        modal.ticket_qty._value = "5"

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await modal.on_submit(interaction)

        mock_send_error_response.assert_awaited_with(
            interaction,
            "**tester** does not have enough ingots for  **5** tickets.\n\n"
            "Cost:  **25,000**\nBalance:  **20,000**\n\n"
            "You can afford a maximum of  **4** tickets.",
        )

        mock_storage.update_members.assert_not_called()
        mock_storage.add_raffle_tickets.assert_not_called()
