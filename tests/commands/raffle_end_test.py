import unittest
from unittest.mock import patch

from ironforgedbot.commands.raffle.raffle_end import sub_raffle_end
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import StorageError
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffleEnd(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.raffle_end.STORAGE")
    async def test_raffleadmin_end_raffle(self, mock_storage):
        interaction = create_mock_discord_interaction()

        user = create_test_member("test", ROLES.LEADERSHIP)
        interaction.user = user

        await sub_raffle_end(interaction)

        mock_storage.end_raffle.assert_called_once_with(user.display_name)
        interaction.followup.send.assert_called_once_with(
            "Raffle ended! Members can no longer purchase tickets."
        )

    @patch("ironforgedbot.commands.raffle.raffle_end.send_error_response")
    @patch("ironforgedbot.commands.raffle.raffle_end.STORAGE")
    async def test_sub_start_raffle_handles_error(
        self, mock_storage, mock_send_error_response
    ):
        interaction = create_mock_discord_interaction()

        user = create_test_member("test", ROLES.LEADERSHIP)
        interaction.user = user

        mock_storage.end_raffle.side_effect = StorageError("Test")

        await sub_raffle_end(interaction)

        interaction.followup.send.assert_not_called()

        mock_send_error_response.assert_awaited_with(
            interaction, "Encountered error ending raffle: Test"
        )
