import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.models.member import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_db_member,
    setup_database_service_mocks,
    assert_embed_structure,
    mock_require_role,
)

with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    from ironforgedbot.commands.ingots.cmd_view_ingots import cmd_view_ingots


class TestCmdViewIngots(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

        self.sample_member = create_test_db_member(
            nickname="TestUser",
            discord_id=12345,
            rank=RANK.IRON,
            ingots=1000,
            id="test-member-id",
        )

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_success_self(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = self.sample_member

        await cmd_view_ingots(self.interaction, None)

        mock_validate.assert_called_once_with(self.interaction.guild, "TestUser")
        mock_member_service.get_member_by_nickname.assert_called_once_with("TestUser")

        # Use helper to validate embed structure
        embed = assert_embed_structure(self, self.interaction)
        self.assertIn("TestUser", embed.title)
        self.assertIn("Ingots", embed.title)

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_success_other_player(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        other_user = create_test_member("OtherUser", [ROLE.MEMBER])
        other_member = create_test_db_member(
            nickname="OtherUser", discord_id=67890, rank=RANK.MITHRIL, ingots=5000
        )

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (other_user, "OtherUser")
        mock_get_rank.return_value = RANK.MITHRIL
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = other_member

        await cmd_view_ingots(self.interaction, "OtherUser")

        mock_validate.assert_called_once_with(self.interaction.guild, "OtherUser")
        mock_member_service.get_member_by_nickname.assert_called_once_with("OtherUser")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("OtherUser", sent_embed.title)
        self.assertEqual(len(sent_embed.fields), 2)

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.send_error_response")
    async def test_cmd_view_ingots_member_not_found(
        self, mock_send_error, mock_validate, mock_member_service_class, mock_db
    ):
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (self.test_user, "UnknownUser")

        mock_member_service.get_member_by_nickname.return_value = None

        await cmd_view_ingots(self.interaction, "UnknownUser")

        mock_send_error.assert_called_once_with(
            self.interaction, "Member 'UnknownUser' could not be found."
        )

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.send_error_response")
    async def test_cmd_view_ingots_validation_error(
        self, mock_send_error, mock_validate
    ):
        mock_validate.side_effect = Exception("Invalid player name")

        await cmd_view_ingots(self.interaction, "BadName")

        mock_send_error.assert_called_once_with(self.interaction, "Invalid player name")

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_embed_fields(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (self.test_user, "TestUser")
        mock_get_rank.return_value = RANK.IRON
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = self.sample_member

        await cmd_view_ingots(self.interaction, "TestUser")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]

        self.assertEqual(len(sent_embed.fields), 2)
        self.assertEqual(sent_embed.fields[0].name, "Account ID")
        self.assertEqual(sent_embed.fields[0].value, "-member-id")
        self.assertEqual(sent_embed.fields[1].name, "Balance")
        self.assertEqual(sent_embed.fields[1].value, ":Ingot: 1,000")

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_zero_ingots_thumbnail(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        zero_ingot_member = create_test_db_member(
            nickname="ZeroUser", discord_id=12345, rank=RANK.IRON, ingots=0
        )

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (self.test_user, "ZeroUser")
        mock_get_rank.return_value = RANK.IRON
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = zero_ingot_member

        await cmd_view_ingots(self.interaction, "ZeroUser")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertEqual(sent_embed.thumbnail.url, "")

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_high_ingots_thumbnail(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        rich_member = create_test_db_member(
            nickname="RichUser", discord_id=12345, rank=RANK.IRON, ingots=25_000_000
        )

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (self.test_user, "RichUser")
        mock_get_rank.return_value = RANK.IRON
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = rich_member

        await cmd_view_ingots(self.interaction, "RichUser")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("Platinum_token_detail.png", sent_embed.thumbnail.url)

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_various_thresholds(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        test_cases = [
            (100_000, "Coins_5_detail.png"),
            (350_000, "Coins_25_detail.png"),
            (750_000, "Coins_100_detail.png"),
            (2_500_000, "Coins_250_detail.png"),
            (5_000_000, "Coins_1000_detail.png"),
            (10_000_000, "Platinum_token_3_detail.png"),
            (15_000_000, "Platinum_token_4_detail.png"),
        ]

        for ingots, expected_image in test_cases:
            with self.subTest(ingots=ingots):
                test_member = Member(
                    id="test-member-id",
                    discord_id=12345,
                    active=True,
                    nickname="TestUser",
                    ingots=ingots,
                    rank=RANK.IRON,
                )

                mock_db_session, mock_member_service = setup_database_service_mocks(
                    mock_db, mock_member_service_class
                )
                mock_validate.return_value = (self.test_user, "TestUser")
                mock_get_rank.return_value = RANK.IRON
                mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

                mock_member_service.get_member_by_nickname.return_value = test_member

                await cmd_view_ingots(self.interaction, "TestUser")

                sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
                self.assertIn(expected_image, sent_embed.thumbnail.url)

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_large_ingot_formatting(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        large_ingot_member = Member(
            id="large-member-id",
            discord_id=12345,
            active=True,
            nickname="LargeUser",
            ingots=1_234_567,
            rank=RANK.IRON,
        )

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_validate.return_value = (self.test_user, "LargeUser")
        mock_get_rank.return_value = RANK.IRON
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = large_ingot_member

        await cmd_view_ingots(self.interaction, "LargeUser")

        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        balance_field = sent_embed.fields[1]
        self.assertEqual(balance_field.value, ":Ingot: 1,234,567")

    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.db")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.MemberService")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.validate_playername")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.get_rank_from_member")
    @patch("ironforgedbot.commands.ingots.cmd_view_ingots.find_emoji")
    async def test_cmd_view_ingots_uses_validated_player_not_display_name(
        self,
        mock_find_emoji,
        mock_get_rank,
        mock_validate,
        mock_member_service_class,
        mock_db,
    ):
        """Test that the validated player name is used for DB lookup, not display name."""
        # Create a discord member with a different display name than their validated player name
        discord_member = create_test_member("Display Name With Spaces", [ROLE.MEMBER])
        validated_player_name = "ValidatedName"

        db_member = create_test_db_member(
            nickname=validated_player_name,
            discord_id=12345,
            rank=RANK.IRON,
            ingots=1000,
        )

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        # validate_playername returns the validated player name, not the display name
        mock_validate.return_value = (discord_member, validated_player_name)
        mock_get_rank.return_value = RANK.IRON
        mock_find_emoji.side_effect = lambda x: f":{x}:" if x else ""

        mock_member_service.get_member_by_nickname.return_value = db_member

        await cmd_view_ingots(self.interaction, "some input")

        # Assert that the DB service was called with the validated player name, not display name
        mock_member_service.get_member_by_nickname.assert_called_once_with(
            validated_player_name
        )

        # Verify the display name is still used in the embed title
        sent_embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("Display Name With Spaces", sent_embed.title)
