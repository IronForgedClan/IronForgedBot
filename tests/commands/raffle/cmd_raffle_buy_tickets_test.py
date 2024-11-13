import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.raffle.cmd_raffle_buy_tickets import cmd_buy_raffle_tickets
from ironforgedbot.common.roles import ROLE
from ironforgedbot.storage.types import Member
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffleBuyTickets(unittest.IsolatedAsyncioTestCase):
    @patch(
        "ironforgedbot.commands.raffle.cmd_raffle_buy_tickets.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_buy_raffle_tickets(self, mock_storage):
        caller = create_test_member("tester", ROLE.MEMBER)
        interaction = create_mock_discord_interaction(user=caller)

        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=caller.display_name, ingots=25000
        )

        await cmd_buy_raffle_tickets(interaction, 1)

        interaction.followup.send.assert_called_once_with(
            f"{caller.display_name} successfully bought 1 tickets for 5000 ingots!"
        )

    @patch(
        "ironforgedbot.commands.raffle.cmd_raffle_buy_tickets.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_buy_raffle_tickets_not_enough_ingots(self, mock_storage):
        caller = create_test_member("tester", ROLE.MEMBER)
        interaction = create_mock_discord_interaction(user=caller)

        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=caller.display_name, ingots=5000
        )

        await cmd_buy_raffle_tickets(interaction, 5)

        interaction.followup.send.assert_called_once_with(
            f"""{caller.display_name} does not have enough ingots for 5 tickets.
Cost: 25000, current ingots: 5000"""
        )
