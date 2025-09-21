import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from tabulate import tabulate

from ironforgedbot.common.roles import ROLE
from ironforgedbot.services.ingot_service import IngotServiceResponse
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    setup_database_service_mocks,
    assert_embed_structure,
    mock_require_role,
)

with patch("ironforgedbot.decorators.require_role", mock_require_role):
    from ironforgedbot.commands.ingots.cmd_add_remove_ingots import (
        cmd_add_remove_ingots,
    )


class TestCmdAddRemoveIngots(unittest.IsolatedAsyncioTestCase):
    def setUp(self):

        self.caller = create_test_member("leader", [ROLE.LEADERSHIP])
        self.target1 = create_test_member("player1", [ROLE.MEMBER])
        self.target2 = create_test_member("player2", [ROLE.MEMBER])
        self.target3 = create_test_member("player3", [ROLE.MEMBER])

        self.interaction = create_mock_discord_interaction(
            user=self.caller, members=[self.target1, self.target2, self.target3]
        )

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_add_single_player(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_add_ingots.return_value = IngotServiceResponse(
            True, "Ingots added successfully", 10000
        )

        await cmd_add_remove_ingots(self.interaction, "player1", 5000, "testing")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "player1", must_be_member=True
        )
        mock_ingot_service.try_add_ingots.assert_called_once_with(
            self.target1.id, 5000, self.caller.id, "testing"
        )

        embed = assert_embed_structure(self, self.interaction)
        self.assertIn("Add Ingots Result", embed.title)
        self.assertIn("+5,000", embed.description)
        self.assertIn("testing", embed.description)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_remove_single_player(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed successfully", 3000
        )

        await cmd_add_remove_ingots(self.interaction, "player1", -2000, "penalty")

        mock_validate.assert_called_once_with(
            self.interaction.guild, "player1", must_be_member=True
        )
        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            self.target1.id, -2000, self.caller.id, "penalty"
        )

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("Remove Ingots Result", sent_embed.title)
        self.assertIn("-2,000", sent_embed.description)
        self.assertIn("penalty", sent_embed.description)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_multiple_players(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_find_emoji.return_value = ":Ingot:"

        validate_responses = [
            (self.target1, "player1"),
            (self.target2, "player2"),
        ]
        mock_validate.side_effect = validate_responses

        service_responses = [
            IngotServiceResponse(True, "Success", 8000),
            IngotServiceResponse(True, "Success", 12000),
        ]
        mock_ingot_service.try_add_ingots.side_effect = service_responses

        await cmd_add_remove_ingots(self.interaction, "player1,player2", 3000, "bonus")

        self.assertEqual(mock_validate.call_count, 2)
        self.assertEqual(mock_ingot_service.try_add_ingots.call_count, 2)

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("Add Ingots Result", sent_embed.title)
        self.assertIn("+6,000", sent_embed.description)  # Total change: 3000 * 2

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_duplicate_players_ignored(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_add_ingots.return_value = IngotServiceResponse(
            True, "Success", 8000
        )

        await cmd_add_remove_ingots(
            self.interaction, "player1,player1,player1", 3000, "bonus"
        )

        mock_validate.assert_called_once()  # Only called once despite 3 names
        mock_ingot_service.try_add_ingots.assert_called_once()

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("+3,000", sent_embed.description)  # Only one player processed

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_unknown_players_handled(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_find_emoji.return_value = ":Ingot:"

        def validate_side_effect(guild, player_name, must_be_member=False):
            if player_name == "player1":
                return (self.target1, "player1")
            elif player_name == "unknown":
                raise ValueError("Unknown player")

        mock_validate.side_effect = validate_side_effect

        mock_ingot_service.try_add_ingots.return_value = IngotServiceResponse(
            True, "Success", 8000
        )

        await cmd_add_remove_ingots(self.interaction, "player1,unknown", 3000, "bonus")

        self.assertEqual(mock_validate.call_count, 2)
        mock_ingot_service.try_add_ingots.assert_called_once()  # Only valid player processed

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        embed_field_value = sent_embed.fields[0].value
        self.assertIn("unknown", embed_field_value)
        self.assertIn("0", embed_field_value)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_insufficient_funds(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            False, "Insufficient funds", 1000
        )

        await cmd_add_remove_ingots(self.interaction, "player1", -5000, "penalty")

        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            self.target1.id, -5000, self.caller.id, "penalty"
        )

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        embed_field_value = sent_embed.fields[0].value
        self.assertIn("player1", embed_field_value)
        self.assertIn("0", embed_field_value)  # No change due to insufficient funds

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_embed_structure(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_add_ingots.return_value = IngotServiceResponse(
            True, "Success", 10000
        )

        await cmd_add_remove_ingots(self.interaction, "player1", 5000, "testing")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]

        self.assertEqual(len(sent_embed.fields), 1)
        embed_field = sent_embed.fields[0]
        self.assertEqual(embed_field.name, "")
        self.assertIn("```", embed_field.value)  # Should be code block
        self.assertIn("Player", embed_field.value)  # Table headers
        self.assertIn("Change", embed_field.value)
        self.assertIn("Total", embed_field.value)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.datetime")
    async def test_cmd_add_remove_ingots_large_result_file_output(
        self,
        mock_datetime,
        mock_find_emoji,
        mock_validate,
        mock_create_ingot_service,
        mock_db,
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_find_emoji.return_value = ":Ingot:"
        mock_datetime.now.return_value.strftime.return_value = "20250101_120000"

        # Create 10 players to trigger file output (>= 9 results)
        players = [f"player{i}" for i in range(10)]
        validate_responses = [
            (create_test_member(name, [ROLE.MEMBER]), name) for name in players
        ]
        mock_validate.side_effect = validate_responses

        service_responses = [
            IngotServiceResponse(True, "Success", 8000) for _ in range(10)
        ]
        mock_ingot_service.try_add_ingots.side_effect = service_responses

        await cmd_add_remove_ingots(self.interaction, ",".join(players), 3000, "bonus")

        # Should send file instead of embed
        call_args = self.interaction.followup.send.call_args
        self.assertIsNone(call_args.kwargs.get("embed"))
        self.assertIsNotNone(call_args.kwargs.get("file"))

        sent_file = call_args.kwargs["file"]
        self.assertIn("ingot_results_20250101_120000.txt", sent_file.filename)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_empty_players_ignored(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_add_ingots.return_value = IngotServiceResponse(
            True, "Success", 8000
        )

        # Include empty strings and whitespace
        await cmd_add_remove_ingots(self.interaction, "player1, , ,  ", 3000, "bonus")

        mock_validate.assert_called_once()  # Only called for valid player
        mock_ingot_service.try_add_ingots.assert_called_once()

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_result_sorting(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_find_emoji.return_value = ":Ingot:"

        # Create players in non-alphabetical order
        players = ["zebra", "alpha", "beta"]
        validate_responses = [
            (create_test_member(name, [ROLE.MEMBER]), name) for name in players
        ]
        mock_validate.side_effect = validate_responses

        service_responses = [
            IngotServiceResponse(True, "Success", 8000) for _ in range(3)
        ]
        mock_ingot_service.try_add_ingots.side_effect = service_responses

        await cmd_add_remove_ingots(self.interaction, ",".join(players), 3000, "bonus")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        embed_field_value = sent_embed.fields[0].value

        # Results should be sorted alphabetically
        alpha_pos = embed_field_value.find("alpha")
        beta_pos = embed_field_value.find("beta")
        zebra_pos = embed_field_value.find("zebra")

        self.assertLess(alpha_pos, beta_pos)
        self.assertLess(beta_pos, zebra_pos)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.create_ingot_service")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.find_emoji")
    async def test_cmd_add_remove_ingots_large_numbers_formatting(
        self, mock_find_emoji, mock_validate, mock_create_ingot_service, mock_db
    ):
        mock_db_session, mock_ingot_service = setup_database_service_mocks(
            mock_db, mock_create_ingot_service
        )
        mock_validate.return_value = (self.target1, "player1")
        mock_find_emoji.return_value = ":Ingot:"

        mock_ingot_service.try_add_ingots.return_value = IngotServiceResponse(
            True, "Success", 1_234_567
        )

        await cmd_add_remove_ingots(self.interaction, "player1", 1_000_000, "big bonus")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]

        # Check that large numbers are formatted with commas
        self.assertIn("+1,000,000", sent_embed.description)
        embed_field_value = sent_embed.fields[0].value
        self.assertIn("1,234,567", embed_field_value)
