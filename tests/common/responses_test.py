import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta, timezone

import discord

from ironforgedbot.common.responses import (
    send_error_response,
    build_error_message_string,
    build_response_embed,
    build_ingot_response_embed,
    send_prospect_response,
    send_member_no_hiscore_values,
    send_not_clan_member,
)
from ironforgedbot.common.roles import ROLE
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestResponses(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_member = create_test_member("TestUser", [ROLE.MEMBER])
        self.mock_member.id = 12345
        self.mock_interaction = create_mock_discord_interaction(user=self.mock_member)

        self.mock_db_member = Mock()
        self.mock_db_member.nickname = "TestPlayer"
        self.mock_db_member.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    async def test_send_error_response(self):
        await send_error_response(self.mock_interaction, "Test error message")

        self.mock_interaction.followup.send.assert_called_once()
        call_args = self.mock_interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]

        self.assertEqual(embed.title, ":exclamation: Error")
        self.assertEqual(embed.description, "Test error message")
        self.assertEqual(embed.color, discord.Colour.red())

    def test_build_error_message_string(self):
        result = build_error_message_string("Test message")
        expected = ":warning:\nTest message"
        self.assertEqual(result, expected)

    def test_build_response_embed(self):
        title = "Test Title"
        description = "Test Description"
        color = discord.Color.blue()

        result = build_response_embed(title, description, color)

        self.assertIsInstance(result, discord.Embed)
        self.assertEqual(result.title, title)
        self.assertEqual(result.description, description)
        self.assertEqual(result.color, color)

    def test_build_ingot_response_embed(self):
        title = "Ingot Title"
        description = "Ingot Description"

        result = build_ingot_response_embed(title, description)

        self.assertIsInstance(result, discord.Embed)
        self.assertEqual(result.title, title)
        self.assertEqual(result.description, description)
        self.assertEqual(result.color, discord.Colour.light_grey())

    @patch("ironforgedbot.common.responses.find_emoji")
    @patch("ironforgedbot.common.responses.text_bold")
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.responses.db")
    @patch("ironforgedbot.common.responses.create_member_service")
    async def test_send_prospect_response_success(
        self,
        mock_create_member_service,
        mock_db,
        mock_build_embed,
        mock_text_bold,
        mock_find_emoji,
    ):
        mock_find_emoji.return_value = "🔸"
        mock_text_bold.side_effect = lambda x: f"**{x}**"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id.return_value = self.mock_db_member
        mock_create_member_service.return_value = mock_member_service

        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        # Mock datetime.now to return a specific date for predictable testing
        with patch("ironforgedbot.common.responses.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            await send_prospect_response(
                self.mock_interaction, "Iron", "⚪", self.mock_member
            )

        mock_member_service.get_member_by_discord_id.assert_called_once_with(12345)
        mock_build_embed.assert_called_once()

        call_args = mock_build_embed.call_args
        self.assertEqual(call_args[0][0], "")  # title
        self.assertIn(
            "**TestPlayer**", call_args[0][1]
        )  # description contains member name
        self.assertIn("**Prospect**", call_args[0][1])  # description contains role
        self.assertEqual(call_args[0][2], discord.Color.from_str("#df781c"))  # color

        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.common.responses.send_error_response")
    @patch("ironforgedbot.common.responses.db")
    @patch("ironforgedbot.common.responses.create_member_service")
    async def test_send_prospect_response_member_not_found(
        self, mock_create_member_service, mock_db, mock_send_error
    ):
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id.return_value = None
        mock_create_member_service.return_value = mock_member_service

        await send_prospect_response(
            self.mock_interaction, "Iron", "⚪", self.mock_member
        )

        mock_send_error.assert_called_once_with(
            self.mock_interaction, "Member not found in database."
        )

    @patch("ironforgedbot.common.responses.find_emoji")
    @patch("ironforgedbot.common.responses.get_rank_from_points")
    @patch("ironforgedbot.common.responses.get_rank_color_from_points")
    @patch("ironforgedbot.common.responses.text_bold")
    @patch("ironforgedbot.common.responses.build_response_embed")
    async def test_send_member_no_hiscore_values(
        self,
        mock_build_embed,
        mock_text_bold,
        mock_get_rank_color,
        mock_get_rank,
        mock_find_emoji,
    ):
        mock_get_rank.return_value = "Bronze"
        mock_get_rank_color.return_value = discord.Color.orange()
        mock_find_emoji.return_value = "🥉"
        mock_text_bold.return_value = "**Bronze**"

        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        await send_member_no_hiscore_values(self.mock_interaction, "TestPlayer")

        mock_get_rank.assert_called_once_with(0)
        mock_get_rank_color.assert_called_once_with(0)
        mock_find_emoji.assert_called_once_with("Bronze")

        mock_build_embed.assert_called_once()
        call_args = mock_build_embed.call_args
        self.assertEqual(call_args[0][0], "🥉 TestPlayer")  # title
        self.assertIn(
            "Unable to calculate an accurate score", call_args[0][1]
        )  # description
        self.assertEqual(call_args[0][2], discord.Color.orange())  # color

        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.common.responses.text_bold")
    @patch("ironforgedbot.common.responses.build_response_embed")
    async def test_send_not_clan_member_with_points(
        self, mock_build_embed, mock_text_bold
    ):
        mock_text_bold.side_effect = lambda x: f"**{x}**"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        await send_not_clan_member(
            self.mock_interaction,
            "Iron",
            "⚪",
            discord.Color.dark_gray(),
            1000,
            "TestPlayer",
        )

        mock_build_embed.assert_called_once()
        call_args = mock_build_embed.call_args
        self.assertEqual(call_args[0][0], "⚪ TestPlayer")  # title
        self.assertIn(
            "This player is not a member of the clan", call_args[0][1]
        )  # description
        self.assertIn("**Iron Forged**", call_args[0][1])  # clan name
        self.assertIn("**Iron**", call_args[0][1])  # rank name
        self.assertEqual(call_args[0][2], discord.Color.dark_gray())  # color

        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.common.responses.text_sub")
    @patch("ironforgedbot.common.responses.build_response_embed")
    async def test_send_not_clan_member_no_points(
        self, mock_build_embed, mock_text_sub
    ):
        mock_text_sub.return_value = "*...do any of us?*"
        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        await send_not_clan_member(
            self.mock_interaction,
            "Iron",
            "⚪",
            discord.Color.dark_gray(),
            0,
            "TestPlayer",
        )

        mock_build_embed.assert_called_once()
        call_args = mock_build_embed.call_args
        self.assertEqual(
            call_args[0][0], ":grey_question: TestPlayer"
        )  # title with question mark
        self.assertIn(
            "Unable to calculate an accurate score", call_args[0][1]
        )  # description
        self.assertIn("Do they exist?", call_args[0][1])  # existential question
        self.assertEqual(call_args[0][2], discord.Color.dark_gray())  # color

        mock_text_sub.assert_called_once_with("...do any of us?")
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.common.responses.find_emoji")
    @patch("ironforgedbot.common.responses.text_bold")
    @patch("ironforgedbot.common.responses.build_response_embed")
    @patch("ironforgedbot.common.responses.db")
    @patch("ironforgedbot.common.responses.create_member_service")
    async def test_send_prospect_response_days_calculation(
        self,
        mock_create_member_service,
        mock_db,
        mock_build_embed,
        mock_text_bold,
        mock_find_emoji,
    ):
        mock_find_emoji.return_value = "🔸"
        mock_text_bold.side_effect = lambda x: f"**{x}**"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id.return_value = self.mock_db_member
        mock_create_member_service.return_value = mock_member_service

        mock_embed = Mock()
        mock_build_embed.return_value = mock_embed

        # Mock datetime.now to return a specific date for predictable testing
        with patch("ironforgedbot.common.responses.datetime") as mock_datetime:
            # Set current time to January 5, 2024 (4 days after joined date)
            mock_datetime.now.return_value = datetime(2024, 1, 5, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            await send_prospect_response(
                self.mock_interaction, "Iron", "⚪", self.mock_member
            )

        call_args = mock_build_embed.call_args
        description = call_args[0][1]
        # With joined date Jan 1 and current date Jan 5, should show 10 days remaining
        self.assertIn("**10 days**", description)

    def test_build_response_embed_different_colors(self):
        colors = [
            discord.Color.red(),
            discord.Color.green(),
            discord.Color.blue(),
            discord.Color.purple(),
            discord.Color.from_str("#ff5733"),
        ]

        for color in colors:
            embed = build_response_embed("Test", "Description", color)
            self.assertEqual(embed.color, color)
