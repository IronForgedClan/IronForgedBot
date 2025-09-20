import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord


def mock_require_role(role, ephemeral=False):
    def decorator(func):
        return func
    return decorator


def mock_require_channel(channels):
    def decorator(func):
        return func
    return decorator


with patch("ironforgedbot.decorators.require_role", mock_require_role), \
     patch("ironforgedbot.decorators.require_channel", mock_require_channel):
    from ironforgedbot.commands.raffle.cmd_raffle import cmd_raffle, build_embed


class TestCmdRaffle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_interaction = Mock(spec=discord.Interaction)
        self.mock_interaction.guild = Mock()
        self.mock_interaction.user = Mock()
        self.mock_interaction.user.id = 12345
        self.mock_interaction.followup.send = AsyncMock()
        
        self.mock_member = Mock()
        self.mock_member.id = 12345
        self.mock_interaction.guild.get_member.return_value = self.mock_member
    @patch("ironforgedbot.commands.raffle.cmd_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.build_response_embed")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.STATE")
    async def test_build_embed_raffle_offline(self, mock_state, mock_build_embed, mock_find_emoji):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}
        mock_find_emoji.return_value = "🎫"
        
        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed
        
        result = await build_embed(self.mock_interaction)
        
        mock_build_embed.assert_called_once_with(
            title="🎫 Iron Forged Raffle",
            description="",
            color=discord.Colour.red()
        )
        mock_embed.add_field.assert_called_once_with(
            name="Raffle Status",
            value="🔴 OFFLINE",
            inline=False
        )
        mock_embed.set_thumbnail.assert_called_once()
        self.assertEqual(result, mock_embed)

    @patch("ironforgedbot.commands.raffle.cmd_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.build_response_embed")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.db")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.RaffleService")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.STATE")
    async def test_build_embed_raffle_online_no_user_tickets(self, mock_state, mock_service_class, mock_db, mock_build_embed, mock_find_emoji):
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_find_emoji.side_effect = lambda name: "🎫" if name == "Raffle_Ticket" else "💰"
        
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        
        mock_service = AsyncMock()
        mock_service.get_member_ticket_total.return_value = 0
        mock_service.get_raffle_ticket_total.return_value = 150
        mock_service_class.return_value = mock_service
        
        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed
        
        result = await build_embed(self.mock_interaction)
        
        mock_build_embed.assert_called_once_with(
            title="🎫 Iron Forged Raffle",
            description="",
            color=discord.Colour.green()
        )
        
        expected_calls = [
            unittest.mock.call(name="Raffle Status", value="🟢 ONLINE", inline=False),
            unittest.mock.call(name="Ticket Price", value="💰 5,000", inline=True),
            unittest.mock.call(name="My Tickets", value="🎫 0", inline=True),
            unittest.mock.call(name="Prize Pool", value="💰 375,000", inline=True)
        ]
        mock_embed.add_field.assert_has_calls(expected_calls)
        
        mock_service.get_member_ticket_total.assert_called_once_with(12345)
        mock_service.get_raffle_ticket_total.assert_called_once()
        self.assertEqual(result, mock_embed)

    @patch("ironforgedbot.commands.raffle.cmd_raffle.find_emoji")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.build_response_embed")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.db")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.RaffleService")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.STATE")
    async def test_build_embed_raffle_online_with_user_tickets(self, mock_state, mock_service_class, mock_db, mock_build_embed, mock_find_emoji):
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_find_emoji.side_effect = lambda name: "🎫" if name == "Raffle_Ticket" else "💰"
        
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        
        mock_service = AsyncMock()
        mock_service.get_member_ticket_total.return_value = 10
        mock_service.get_raffle_ticket_total.return_value = 160
        mock_service_class.return_value = mock_service
        
        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed
        
        result = await build_embed(self.mock_interaction)
        
        expected_calls = [
            unittest.mock.call(name="Raffle Status", value="🟢 ONLINE", inline=False),
            unittest.mock.call(name="Ticket Price", value="💰 5,000", inline=True),
            unittest.mock.call(name="My Tickets", value="🎫 10", inline=True),
            unittest.mock.call(name="Prize Pool", value="💰 400,000", inline=True)
        ]
        mock_embed.add_field.assert_has_calls(expected_calls)
        self.assertEqual(result, mock_embed)
    
    @patch("ironforgedbot.commands.raffle.cmd_raffle.send_error_response")
    async def test_cmd_raffle_member_not_found(self, mock_send_error):
        self.mock_interaction.guild.get_member.return_value = None
        
        with patch("ironforgedbot.commands.raffle.cmd_raffle.build_embed") as mock_build_embed:
            mock_build_embed.return_value = Mock()
            await cmd_raffle(self.mock_interaction)
        
        mock_send_error.assert_called_once_with(
            self.mock_interaction, "Unable to get member details."
        )
    
    @patch("ironforgedbot.commands.raffle.cmd_raffle.RaffleMenuView")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.check_member_has_role")
    async def test_cmd_raffle_success_member_user(self, mock_check_role, mock_menu_class):
        mock_check_role.return_value = False
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_embed = Mock()
        with patch("ironforgedbot.commands.raffle.cmd_raffle.build_embed") as mock_build_embed:
            mock_build_embed.return_value = mock_embed
            await cmd_raffle(self.mock_interaction)
        
        mock_check_role.assert_called_once()
        mock_menu_class.assert_called_once_with(False)
        self.mock_interaction.followup.send.assert_called_once_with(
            embed=mock_embed, view=mock_menu
        )
    
    @patch("ironforgedbot.commands.raffle.cmd_raffle.RaffleMenuView")
    @patch("ironforgedbot.commands.raffle.cmd_raffle.check_member_has_role")
    async def test_cmd_raffle_success_leadership_user(self, mock_check_role, mock_menu_class):
        mock_check_role.return_value = True
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_embed = Mock()
        with patch("ironforgedbot.commands.raffle.cmd_raffle.build_embed") as mock_build_embed:
            mock_build_embed.return_value = mock_embed
            await cmd_raffle(self.mock_interaction)
        
        mock_menu_class.assert_called_once_with(True)
        self.mock_interaction.followup.send.assert_called_once_with(
            embed=mock_embed, view=mock_menu
        )
    
    async def test_cmd_raffle_build_embed_returns_none(self):
        with patch("ironforgedbot.commands.raffle.cmd_raffle.build_embed") as mock_build_embed:
            mock_build_embed.return_value = None
            result = await cmd_raffle(self.mock_interaction)
        
        self.assertIsNone(result)
        self.mock_interaction.followup.send.assert_not_called()
