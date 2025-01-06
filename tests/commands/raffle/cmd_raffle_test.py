import unittest
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.commands.raffle.cmd_raffle import build_embed
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffle(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.cmd_raffle.STATE")
    async def test_build_embed_raffle_offline(self, mock_state):
        mock_state.state = {"raffle_on": False, "raffle_price": 0}

        expected_title = " Iron Forged Raffle"
        expected_description = ""
        expected_fields = [("Raffle Status", "🔴 OFFLINE", False)]

        interaction = create_mock_discord_interaction()
        result = await build_embed(interaction)

        assert result
        self.assertIsInstance(result, discord.Embed)
        self.assertEqual(result.title, expected_title)
        self.assertEqual(result.description, expected_description)
        self.assertEqual(result.color, discord.Color.red())

        self.assertEqual(len(result.fields), len(expected_fields))
        for i, field in enumerate(expected_fields):
            self.assertEqual(result.fields[i].name, field[0])
            self.assertEqual(result.fields[i].value, field[1])
            self.assertEqual(result.fields[i].inline, field[2])

    @patch("ironforgedbot.commands.raffle.cmd_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.cmd_raffle.STATE")
    async def test_build_embed_raffle_online(self, mock_state, mock_storage):
        interaction = create_mock_discord_interaction()

        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_storage.read_raffle_tickets.return_value = {1: 100, 2: 50}

        expected_title = " Iron Forged Raffle"
        expected_description = ""
        expected_fields = [
            ("Raffle Status", "🟢 ONLINE", False),
            ("Ticket Price", " 5,000", True),
            ("My Tickets", " 0", True),
            ("Prize Pool", " 375,000", True),
        ]

        result = await build_embed(interaction)

        assert result
        self.assertIsInstance(result, discord.Embed)
        self.assertEqual(result.title, expected_title)
        self.assertEqual(result.description, expected_description)
        self.assertEqual(result.color, discord.Color.green())

        self.assertEqual(len(result.fields), len(expected_fields))
        for i, field in enumerate(expected_fields):
            self.assertEqual(result.fields[i].name, field[0])
            self.assertEqual(result.fields[i].value, field[1])
            self.assertEqual(result.fields[i].inline, field[2])

    @patch("ironforgedbot.commands.raffle.cmd_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.cmd_raffle.STATE")
    async def test_build_embed_raffle_online_show_user_ticket_count(
        self, mock_state, mock_storage
    ):
        user = create_test_member("tester", [])
        interaction = create_mock_discord_interaction(user=user)

        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_storage.read_raffle_tickets.return_value = {1: 100, 2: 50, user.id: 10}

        expected_title = " Iron Forged Raffle"
        expected_description = ""
        expected_fields = [
            ("Raffle Status", "🟢 ONLINE", False),
            ("Ticket Price", " 5,000", True),
            ("My Tickets", " 10", True),
            ("Prize Pool", " 400,000", True),
        ]

        result = await build_embed(interaction)

        assert result
        self.assertIsInstance(result, discord.Embed)
        self.assertEqual(result.title, expected_title)
        self.assertEqual(result.description, expected_description)
        self.assertEqual(result.color, discord.Color.green())

        self.assertEqual(len(result.fields), len(expected_fields))
        for i, field in enumerate(expected_fields):
            self.assertEqual(result.fields[i].name, field[0])
            self.assertEqual(result.fields[i].value, field[1])
            self.assertEqual(result.fields[i].inline, field[2])
