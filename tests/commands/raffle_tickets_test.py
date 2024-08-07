import unittest
from unittest.mock import patch

from ironforgedbot.commands.raffle.raffle_tickets import cmd_raffle_tickets
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffleViewTickets(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.raffle_tickets.STORAGE")
    @patch("ironforgedbot.commands.raffle.raffle_tickets.validate_user_request")
    async def test_raffle_tickets(self, mock_validate_user_request, mock_storage):
        interaction = create_mock_discord_interaction()

        member = Member(id=12345, runescape_name="tester")

        mock_validate_user_request.return_value = (
            create_test_member(member.runescape_name, ROLES.MEMBER),
            member.runescape_name,
        )

        mock_storage.read_member.return_value = member
        mock_storage.read_raffle_tickets.return_value = {member.id: 22}

        await cmd_raffle_tickets(interaction)

        interaction.followup.send.assert_called_once_with("tester has 22 tickets!")

    @patch("ironforgedbot.commands.raffle.raffle_tickets.STORAGE")
    @patch("ironforgedbot.commands.raffle.raffle_tickets.send_error_response")
    @patch("ironforgedbot.commands.raffle.raffle_tickets.validate_user_request")
    async def test_raffle_tickets_user_not_found(
        self, mock_validate_user_request, mock_send_error_response, mock_storage
    ):
        interaction = create_mock_discord_interaction()
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            create_test_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage.read_member.return_value = None
        mock_storage.read_raffle_tickets.return_value = {12345: 25}

        await cmd_raffle_tickets(interaction)

        mock_send_error_response.assert_awaited_with(
            interaction,
            f"{player} not found in storage, please reach out to leadership.",
        )
