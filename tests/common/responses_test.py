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

    @patch("ironforgedbot.common.responses._send_error_report")
    async def test_send_error_response(self, mock_send_error_report):
        await send_error_response(self.mock_interaction, "Test error message")

        # Verify the user error response was sent
        self.mock_interaction.followup.send.assert_called_once()
        call_args = self.mock_interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]

        self.assertEqual(embed.title, ":exclamation: Error")
        self.assertEqual(embed.description, "Test error message")
        self.assertEqual(embed.color, discord.Colour.red())

        # Verify the error report was sent
        mock_send_error_report.assert_called_once_with(
            self.mock_interaction, "Test error message"
        )

    @patch("ironforgedbot.common.responses._send_error_report")
    async def test_send_error_response_opt_out(self, mock_send_error_report):
        await send_error_response(
            self.mock_interaction, "Test error message", report_to_channel=False
        )

        # Verify the user error response was sent
        self.mock_interaction.followup.send.assert_called_once()
        call_args = self.mock_interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]

        self.assertEqual(embed.title, ":exclamation: Error")
        self.assertEqual(embed.description, "Test error message")
        self.assertEqual(embed.color, discord.Colour.red())

        # Verify the error report was NOT sent
        mock_send_error_report.assert_not_called()

    @patch("ironforgedbot.common.responses._get_latest_log_lines_file")
    @patch("ironforgedbot.common.responses.check_member_has_role")
    @patch("ironforgedbot.common.responses.get_text_channel")
    async def test_send_error_report_success(
        self, mock_get_text_channel, mock_check_role, mock_get_log_file
    ):
        # Set up mocks
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_get_text_channel.return_value = mock_channel

        # Mock log file
        mock_log_file = Mock()
        mock_get_log_file.return_value = mock_log_file

        # Mock role checking - simulate user has Member role but not Leadership
        mock_check_role.side_effect = lambda member, role: role == ROLE.MEMBER

        # Add mock guild member lookup
        mock_guild_member = Mock()
        self.mock_interaction.guild.get_member.return_value = mock_guild_member

        # Add mock command data with parameters
        self.mock_interaction.data = {
            "options": [
                {"name": "player", "value": "TestPlayer"},
                {"name": "amount", "value": 100},
            ]
        }

        # Import the private function
        from ironforgedbot.common.responses import _send_error_report

        await _send_error_report(self.mock_interaction, "Test error message")

        # Verify channel was found and message was sent with file attachment
        mock_get_text_channel.assert_called_once()
        mock_channel.send.assert_called_once()

        # Verify the send call includes both embed and file
        call_args = mock_channel.send.call_args
        self.assertIn("embed", call_args.kwargs)
        self.assertIn("file", call_args.kwargs)
        self.assertEqual(call_args.kwargs["file"], mock_log_file)

        # Verify the embed structure
        call_args = mock_channel.send.call_args
        embed = call_args.kwargs["embed"]
        self.assertEqual(embed.title, "🚨 Command Error Report")

        # Check role field shows "Member"
        role_field = next(
            (field for field in embed.fields if field.name == "Role"), None
        )
        self.assertIsNotNone(role_field)
        self.assertEqual(role_field.value, "Member")

        # Check parameters field exists and contains our test data
        param_field = next(
            (field for field in embed.fields if field.name == "Parameters"), None
        )
        self.assertIsNotNone(param_field)
        self.assertIn("player", param_field.value)
        self.assertIn("TestPlayer", param_field.value)
        self.assertIn("amount", param_field.value)
        self.assertIn("100", param_field.value)

        # Check timestamp field exists and has proper format
        timestamp_field = next(
            (field for field in embed.fields if field.name == "Timestamp"), None
        )
        self.assertIsNotNone(timestamp_field)
        self.assertIn("UTC", timestamp_field.value)

        # Check error details field still contains the error message
        error_field = next(
            (field for field in embed.fields if field.name == "Error Message"), None
        )
        self.assertIsNotNone(error_field)
        self.assertIn("Test error message", error_field.value)

    @patch("ironforgedbot.common.responses.get_text_channel")
    @patch("ironforgedbot.common.responses.logger")
    async def test_send_error_report_no_channel(
        self, mock_logger, mock_get_text_channel
    ):
        # Return None for no channel found
        mock_get_text_channel.return_value = None

        # Import the private function
        from ironforgedbot.common.responses import _send_error_report

        await _send_error_report(self.mock_interaction, "Test error message")

        # Verify warning was logged
        mock_logger.warning.assert_called_once_with(
            "Unable to find report channel for error reporting"
        )

    @patch("ironforgedbot.common.responses._get_latest_log_lines_file")
    @patch("ironforgedbot.common.responses.check_member_has_role")
    @patch("ironforgedbot.common.responses.get_text_channel")
    async def test_send_error_report_leadership_role(
        self, mock_get_text_channel, mock_check_role, mock_get_log_file
    ):
        # Set up mocks
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_get_text_channel.return_value = mock_channel

        # Mock log file
        mock_log_file = Mock()
        mock_get_log_file.return_value = mock_log_file

        # Mock role checking - simulate user has Leadership role
        mock_check_role.side_effect = lambda member, role: role == ROLE.LEADERSHIP

        # Add mock guild member lookup
        mock_guild_member = Mock()
        self.mock_interaction.guild.get_member.return_value = mock_guild_member
        self.mock_interaction.data = None  # No parameters

        # Import the private function
        from ironforgedbot.common.responses import _send_error_report

        await _send_error_report(self.mock_interaction, "Test error message")

        # Verify the embed structure
        call_args = mock_channel.send.call_args
        embed = call_args.kwargs["embed"]

        # Check role field shows "Leadership"
        role_field = next(
            (field for field in embed.fields if field.name == "Role"), None
        )
        self.assertIsNotNone(role_field)
        self.assertEqual(role_field.value, "Leadership")

        # Check parameters field shows "No parameters"
        param_field = next(
            (field for field in embed.fields if field.name == "Parameters"), None
        )
        self.assertIsNotNone(param_field)
        self.assertEqual(param_field.value, "No parameters")

    @patch("ironforgedbot.common.responses._get_latest_log_lines_file")
    @patch("ironforgedbot.common.responses.check_member_has_role")
    @patch("ironforgedbot.common.responses.get_text_channel")
    async def test_send_error_report_guest_role(
        self, mock_get_text_channel, mock_check_role, mock_get_log_file
    ):
        # Set up mocks
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_get_text_channel.return_value = mock_channel

        # Mock log file
        mock_log_file = Mock()
        mock_get_log_file.return_value = mock_log_file

        # Mock role checking - simulate user has neither Member nor Leadership role
        mock_check_role.return_value = False

        # Add mock guild member lookup
        mock_guild_member = Mock()
        self.mock_interaction.guild.get_member.return_value = mock_guild_member

        # Mock data without options key
        self.mock_interaction.data = {"type": 1}

        # Import the private function
        from ironforgedbot.common.responses import _send_error_report

        await _send_error_report(self.mock_interaction, "Test error message")

        # Verify the embed structure
        call_args = mock_channel.send.call_args
        embed = call_args.kwargs["embed"]

        # Check role field shows "Guest/Other"
        role_field = next(
            (field for field in embed.fields if field.name == "Role"), None
        )
        self.assertIsNotNone(role_field)
        self.assertEqual(role_field.value, "Guest/Other")

        # Check parameters field shows "No parameters" when options key is missing
        param_field = next(
            (field for field in embed.fields if field.name == "Parameters"), None
        )
        self.assertIsNotNone(param_field)
        self.assertEqual(param_field.value, "No parameters")

    @patch("ironforgedbot.common.responses._get_latest_log_lines_file")
    @patch("ironforgedbot.common.responses.check_member_has_role")
    @patch("ironforgedbot.common.responses.get_text_channel")
    async def test_send_error_report_no_log_file(
        self, mock_get_text_channel, mock_check_role, mock_get_log_file
    ):
        # Set up mocks
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_get_text_channel.return_value = mock_channel

        # Mock log file returns None (no log file available)
        mock_get_log_file.return_value = None

        # Mock role checking - simulate user has Member role
        mock_check_role.side_effect = lambda member, role: role == ROLE.MEMBER

        # Add mock guild member lookup
        mock_guild_member = Mock()
        self.mock_interaction.guild.get_member.return_value = mock_guild_member
        self.mock_interaction.data = None

        # Import the private function
        from ironforgedbot.common.responses import _send_error_report

        await _send_error_report(self.mock_interaction, "Test error message")

        # Verify the send call includes embed but no file
        call_args = mock_channel.send.call_args
        self.assertIn("embed", call_args.kwargs)
        self.assertNotIn("file", call_args.kwargs)

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

        with patch("ironforgedbot.common.responses.datetime") as mock_datetime:
            # Set current time to January 5, 2024 (4 days after joined date)
            mock_datetime.now.return_value = datetime(2024, 1, 5, tzinfo=timezone.utc)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            await send_prospect_response(
                self.mock_interaction, "Iron", "⚪", self.mock_member
            )

        call_args = mock_build_embed.call_args
        description = call_args[0][1]
        # With joined date Jan 1 and current date Jan 5, should show 24 days remaining
        self.assertIn("**24 days**", description)

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
