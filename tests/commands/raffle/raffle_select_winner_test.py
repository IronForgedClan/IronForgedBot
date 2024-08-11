import unittest
from unittest.mock import patch

from ironforgedbot.commands.raffle.raffle_select_winner import sub_raffle_select_winner
from ironforgedbot.storage.types import Member, StorageError
from tests.helpers import create_mock_discord_interaction


class TestRaffleSelectWinner(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.raffle_select_winner.STORAGE")
    async def test_sub_select_winner(self, mock_storage):
        interaction = create_mock_discord_interaction()

        member = Member(id=12345, runescape_name="tester")

        mock_storage.read_raffle_tickets.return_value = {member.id: 25}
        mock_storage.read_members.return_value = [member]

        await sub_raffle_select_winner(interaction)

        interaction.followup.send.assert_called_once_with(
            f"{member.runescape_name} has won 62500 ingots out of 25 entries!"
        )

    @patch("ironforgedbot.commands.raffle.raffle_select_winner.send_error_response")
    @patch("ironforgedbot.commands.raffle.raffle_select_winner.STORAGE")
    async def test_sub_select_winner_error_clearing_tickets(
        self, mock_storage, mock_send_error_response
    ):
        interaction = create_mock_discord_interaction()

        member = Member(id=12345, runescape_name="tester")

        mock_storage.read_raffle_tickets.return_value = {member.id: 25}
        mock_storage.read_members.return_value = [member]
        mock_storage.delete_raffle_tickets.side_effect = StorageError("Test")

        await sub_raffle_select_winner(interaction)

        mock_send_error_response.assert_awaited_with(
            interaction, "Encountered error clearing ticket storage: Test"
        )
