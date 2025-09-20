import unittest
from unittest.mock import ANY, AsyncMock, Mock, patch

import discord

from ironforgedbot.commands.raffle.end_raffle import handle_end_raffle, handle_end_raffle_error


class TestEndRaffle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.guild = Mock()
        self.mock_interaction.user = Mock()
        self.mock_interaction.user.id = 12345
        self.mock_interaction.user.display_name = "TestUser"
        self.mock_interaction.response.defer = AsyncMock()
        self.mock_interaction.followup.send = AsyncMock()
        
        self.mock_parent_message = AsyncMock()
        self.mock_parent_message.edit = AsyncMock()
        self.mock_parent_message.delete = AsyncMock()

    @patch("ironforgedbot.commands.raffle.end_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.end_raffle.build_winner_image_file")
    @patch("ironforgedbot.commands.raffle.end_raffle.db")
    @patch("ironforgedbot.commands.raffle.end_raffle.IngotService")
    @patch("ironforgedbot.commands.raffle.end_raffle.MemberService")
    @patch("ironforgedbot.commands.raffle.end_raffle.RaffleService")
    @patch("ironforgedbot.commands.raffle.end_raffle.random")
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_handle_end_raffle_success(self, mock_state, mock_random, mock_raffle_service_class, mock_member_service_class, mock_ingot_service_class, mock_db, mock_build_image, mock_find_emoji):
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_find_emoji.return_value = "🎫"
        
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        
        # Mock ticket data
        mock_ticket = Mock()
        mock_ticket.member_id = "winner-id-123"
        mock_ticket.quantity = 10
        
        mock_raffle_service = AsyncMock()
        mock_raffle_service.get_raffle_ticket_total.return_value = 20
        mock_raffle_service.get_all_valid_raffle_tickets.return_value = [mock_ticket]
        mock_raffle_service.delete_all_tickets = AsyncMock()
        mock_raffle_service_class.return_value = mock_raffle_service
        
        # Mock winner selection
        mock_random.choices.return_value = ["winner-id-123"]
        
        # Mock member data
        mock_winning_member = Mock()
        mock_winning_member.nickname = "WinnerUser"
        mock_winning_member.discord_id = 67890
        
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_id.return_value = mock_winning_member
        mock_member_service_class.return_value = mock_member_service
        
        # Mock ingot service
        mock_result = Mock()
        mock_result.status = True
        
        mock_ingot_service = AsyncMock()
        mock_ingot_service.try_add_ingots.return_value = mock_result
        mock_ingot_service_class.return_value = mock_ingot_service
        
        # Mock image generation
        mock_image = Mock()
        mock_build_image.return_value = mock_image
        
        # Mock guild member
        mock_discord_member = Mock()
        mock_discord_member.mention = "<@67890>"
        self.mock_interaction.guild.get_member.return_value = mock_discord_member
        
        await handle_end_raffle(self.mock_parent_message, self.mock_interaction)
        
        # Verify raffle setup
        self.mock_parent_message.edit.assert_called_once_with(
            content="## Ending raffle\nSelecting winner, standby...",
            embed=None,
            view=None
        )
        
        # Verify services called
        mock_raffle_service.get_raffle_ticket_total.assert_called_once()
        mock_raffle_service.get_all_valid_raffle_tickets.assert_called_once()
        mock_member_service.get_member_by_id.assert_called_once_with("winner-id-123")
        mock_ingot_service.try_add_ingots.assert_called_once_with(
            67890, 50000, None, "Raffle winnings: (50000)"
        )
        mock_raffle_service.delete_all_tickets.assert_called_once()
        
        # Verify state updated
        self.assertFalse(mock_state.state["raffle_on"])
        self.assertEqual(mock_state.state["raffle_price"], 0)
        
        # Verify winner announcement
        self.mock_interaction.followup.send.assert_called_once()
        call_args = self.mock_interaction.followup.send.call_args
        # Check if it's a positional argument or keyword argument
        if "content" in call_args.kwargs:
            content = call_args.kwargs["content"]
        else:
            content = call_args.args[0]
        self.assertIn("Congratulations <@67890>!!", content)
        self.assertIn("50,000", content)
        self.assertEqual(call_args.kwargs["file"], mock_image)

    @patch("ironforgedbot.commands.raffle.end_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.end_raffle.db")
    @patch("ironforgedbot.commands.raffle.end_raffle.RaffleService")
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_handle_end_raffle_no_tickets_sold(self, mock_state, mock_raffle_service_class, mock_db, mock_find_emoji):
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_find_emoji.return_value = "🎫"
        
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        
        mock_raffle_service = AsyncMock()
        mock_raffle_service.get_raffle_ticket_total.return_value = 0
        mock_raffle_service_class.return_value = mock_raffle_service
        
        await handle_end_raffle(self.mock_parent_message, self.mock_interaction)
        
        # Verify state reset
        self.assertFalse(mock_state.state["raffle_on"])
        self.assertEqual(mock_state.state["raffle_price"], 0)
        
        # Verify message sent
        self.mock_interaction.followup.send.assert_called_once()
        call_args = self.mock_interaction.followup.send.call_args
        self.assertIn("No tickets were sold", call_args[1]["content"])
        
        # Note: parent_message.delete() may be called based on implementation details

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.end_raffle.db")
    @patch("ironforgedbot.commands.raffle.end_raffle.RaffleService")
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_handle_end_raffle_no_valid_tickets(self, mock_state, mock_raffle_service_class, mock_db, mock_find_emoji, mock_handle_error):
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_find_emoji.return_value = "🎫"
        
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        
        mock_raffle_service = AsyncMock()
        mock_raffle_service.get_raffle_ticket_total.return_value = 10
        mock_raffle_service.get_all_valid_raffle_tickets.return_value = []
        mock_raffle_service_class.return_value = mock_raffle_service
        
        await handle_end_raffle(self.mock_parent_message, self.mock_interaction)
        
        mock_handle_error.assert_called_once()
        call_args = mock_handle_error.call_args[0]
        self.assertEqual(call_args[1], self.mock_interaction)
        self.assertEqual(call_args[2], "Raffle ended without any valid entries.")

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.end_raffle.db")
    @patch("ironforgedbot.commands.raffle.end_raffle.MemberService")
    @patch("ironforgedbot.commands.raffle.end_raffle.RaffleService")
    @patch("ironforgedbot.commands.raffle.end_raffle.random")
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_handle_end_raffle_winner_not_found(self, mock_state, mock_random, mock_raffle_service_class, mock_member_service_class, mock_db, mock_find_emoji, mock_handle_error):
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_find_emoji.return_value = "🎫"
        
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        
        mock_ticket = Mock()
        mock_ticket.member_id = "invalid-id"
        mock_ticket.quantity = 10
        
        mock_raffle_service = AsyncMock()
        mock_raffle_service.get_raffle_ticket_total.return_value = 20
        mock_raffle_service.get_all_valid_raffle_tickets.return_value = [mock_ticket]
        mock_raffle_service_class.return_value = mock_raffle_service
        
        mock_random.choices.return_value = ["invalid-id"]
        
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_id.return_value = None
        mock_member_service_class.return_value = mock_member_service
        
        await handle_end_raffle(self.mock_parent_message, self.mock_interaction)
        
        mock_handle_error.assert_called_once()
        call_args = mock_handle_error.call_args[0]
        self.assertIn("Error finding winner's details", call_args[2])

    @patch("ironforgedbot.commands.raffle.end_raffle.send_error_response")
    async def test_handle_end_raffle_error_with_parent_message(self, mock_send_error):
        await handle_end_raffle_error(self.mock_parent_message, self.mock_interaction, "Test error")
        
        self.mock_parent_message.delete.assert_called_once()
        mock_send_error.assert_called_once_with(self.mock_interaction, "Test error")

    @patch("ironforgedbot.commands.raffle.end_raffle.send_error_response")
    async def test_handle_end_raffle_error_without_parent_message(self, mock_send_error):
        await handle_end_raffle_error(None, self.mock_interaction, "Test error")
        
        mock_send_error.assert_called_once_with(self.mock_interaction, "Test error")