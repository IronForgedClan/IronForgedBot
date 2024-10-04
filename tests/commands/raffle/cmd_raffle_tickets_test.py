import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.raffle.cmd_raffle_tickets import cmd_raffle_tickets
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffleViewTickets(unittest.IsolatedAsyncioTestCase):
    @patch(
        "ironforgedbot.commands.raffle.cmd_raffle_tickets.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_raffle_tickets(self, mock_storage):
        caller = create_test_member("tester", ROLES.MEMBER)
        interaction = create_mock_discord_interaction(user=caller)

        member = Member(id=12345, runescape_name=caller.display_name)

        mock_storage.read_member.return_value = member
        mock_storage.read_raffle_tickets.return_value = {member.id: 22}

        await cmd_raffle_tickets(interaction)

        interaction.followup.send.assert_called_once_with(
            f"{caller.display_name} has 22 tickets!"
        )

    @patch(
        "ironforgedbot.commands.raffle.cmd_raffle_tickets.STORAGE",
        new_callable=AsyncMock,
    )
    @patch("ironforgedbot.commands.raffle.cmd_raffle_tickets.send_error_response")
    async def test_raffle_tickets_user_not_found(
        self, mock_send_error_response, mock_storage
    ):
        caller = create_test_member("tester", ROLES.MEMBER)
        interaction = create_mock_discord_interaction(user=caller)

        mock_storage.read_member.return_value = None
        mock_storage.read_raffle_tickets.return_value = {caller.id: 25}

        await cmd_raffle_tickets(interaction)

        mock_send_error_response.assert_awaited_with(
            interaction,
            f"{caller.display_name} not found in storage, please reach out to leadership.",
        )
