import unittest
from unittest.mock import ANY, AsyncMock, patch

from ironforgedbot.commands.raffle.end_raffle import handle_end_raffle
from ironforgedbot.storage.types import Member, StorageError
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestEndRaffle(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_success(self, mock_state, mock_storage):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.return_value = {caller.id: 10}

        await handle_end_raffle(mock_parent_message, interaction)

        mock_parent_message.edit.assert_called_with(
            content="## Ending raffle\nSelecting winner, standby...",
            embed=None,
            view=None,
        )

        mock_storage.update_members.assert_called_with(
            [storage_member],
            interaction.user.display_name,
            note="[BOT] Raffle winnings (25,000)",
        )

        interaction.followup.send.assert_called_with(
            f"##  Congratulations {caller.mention}!!\n"
            "You have won  **25,000** ingots!\n\n"
            "You spent  **50,000** on  **10** tickets.\n"
            "Resulting in  **-25,000** profit.\n"
            "-# ouch\n\n\n"
            "There were a total of  **10** entries.\n"
            "Thank you everyone for participating!",
            file=ANY,
        )

        mock_storage.delete_raffle_tickets.assert_called_once()
        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_reading_tickets(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.side_effect = StorageError("error")

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once_with(
            ANY, interaction, "Encountered error ending raffle: error"
        )
        mock_storage.update_members.assert_not_called()
        mock_storage.delete_raffle_tickets.assert_not_called()
        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_no_tickets_sold(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.return_value = {}

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once_with(
            ANY, interaction, "Raffle ended without any tickets sold."
        )
        mock_storage.update_members.assert_not_called()
        mock_storage.delete_raffle_tickets.assert_not_called()
        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_reading_members(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.side_effect = StorageError("error")
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.return_value = {caller.id: 50}

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once_with(
            ANY, interaction, "Encountered error reading current members: error"
        )
        mock_storage.update_members.assert_not_called()
        mock_storage.delete_raffle_tickets.assert_not_called()
        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_no_tickets_from_valid_members(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.return_value = {1234: 50}

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once()
        mock_storage.update_members.assert_not_called()
        mock_storage.delete_raffle_tickets.assert_not_called()
        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_error_getting_winning_member(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.side_effect = StorageError("error")
        mock_storage.read_raffle_tickets.return_value = {caller.id: 50}

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once_with(ANY, interaction, "error")
        mock_storage.update_members.assert_not_called()
        mock_storage.delete_raffle_tickets.assert_not_called()
        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_awarding_winnings(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.return_value = {caller.id: 50}

        mock_storage.update_members.side_effect = StorageError("error")

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once_with(ANY, interaction, "error")
        mock_storage.delete_raffle_tickets.assert_not_called()
        self.assertEqual(mock_state.state["raffle_on"], True)
        self.assertEqual(mock_state.state["raffle_price"], 5000)

    @patch("ironforgedbot.commands.raffle.end_raffle.handle_end_raffle_error")
    @patch("ironforgedbot.commands.raffle.end_raffle.STORAGE", new_callable=AsyncMock)
    @patch("ironforgedbot.commands.raffle.end_raffle.STATE")
    async def test_end_raffle_fails_clearing_raffle_tickets(
        self, mock_state, mock_storage, mock_handle_error
    ):
        caller = create_test_member("tester", [], "tester")
        mock_state.state = {"raffle_on": True, "raffle_price": 5000}
        mock_parent_message = AsyncMock()

        interaction = create_mock_discord_interaction(user=caller)
        interaction.followup = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()

        storage_member = Member(
            id=caller.id, runescape_name=caller.display_name, ingots=30000
        )

        mock_storage.read_members.return_value = [storage_member]
        mock_storage.read_member.return_value = storage_member
        mock_storage.read_raffle_tickets.return_value = {caller.id: 50}

        mock_storage.delete_raffle_tickets.side_effect = StorageError("error")

        await handle_end_raffle(mock_parent_message, interaction)

        mock_handle_error.assert_called_once_with(
            ANY,
            interaction,
            "Encountered error clearing ticket storage: error",
        )
        self.assertEqual(mock_state.state["raffle_on"], False)
        self.assertEqual(mock_state.state["raffle_price"], 0)
