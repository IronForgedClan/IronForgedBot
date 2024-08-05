import unittest
from unittest.mock import patch

from ironforgedbot.commands.raffle.raffle_start import sub_raffle_start
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import StorageError
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRaffleStart(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.raffle_start.STORAGE")
    async def test_sub_start_raffle(self, mock_storage):
        interaction = create_mock_discord_interaction()

        user = create_test_member("test", ROLES.LEADERSHIP)
        interaction.user = user

        await sub_raffle_start(interaction)

        mock_storage.start_raffle.assert_called_once_with(user.display_name)
        interaction.followup.send.assert_called_once_with(
            "Started raffle! Members can now use ingots to purchase tickets."
        )

    @patch("ironforgedbot.commands.raffle.raffle_start.send_error_response")
    @patch("ironforgedbot.commands.raffle.raffle_start.STORAGE")
    async def test_sub_start_raffle_handles_error(
        self, mock_storage, mock_send_error_response
    ):
        interaction = create_mock_discord_interaction()

        user = create_test_member("test", ROLES.LEADERSHIP)
        interaction.user = user

        mock_storage.start_raffle.side_effect = StorageError("Test")

        await sub_raffle_start(interaction)

        interaction.followup.send.assert_not_called()

        mock_send_error_response.assert_awaited_with(
            interaction, "Encountered error starting raffle: Test"
        )
