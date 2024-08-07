import unittest
from unittest.mock import patch

from ironforgedbot.commands.raffle.raffle_buy_tickets import cmd_buy_raffle_tickets
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffleBuyTickets(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.raffle_buy_tickets.STORAGE")
    @patch("ironforgedbot.commands.raffle.raffle_buy_tickets.validate_user_request")
    async def test_buy_raffle_tickets(self, mock_validate_user_request, mock_storage):
        interaction = create_mock_discord_interaction()
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            create_test_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=player, ingots=25000
        )

        await cmd_buy_raffle_tickets(interaction, 1)

        interaction.followup.send.assert_called_once_with(
            f"{player} successfully bought 1 tickets for 5000 ingots!"
        )

    @patch("ironforgedbot.commands.raffle.raffle_buy_tickets.STORAGE")
    @patch("ironforgedbot.commands.raffle.raffle_buy_tickets.validate_user_request")
    async def test_buy_raffle_tickets_not_enough_ingots(
        self, mock_validate_user_request, mock_storage
    ):
        interaction = create_mock_discord_interaction()
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            create_test_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=player, ingots=5000
        )

        await cmd_buy_raffle_tickets(interaction, 5)

        interaction.followup.send.assert_called_once_with(
            f"""{player} does not have enough ingots for 5 tickets.
Cost: 25000, current ingots: 5000"""
        )
