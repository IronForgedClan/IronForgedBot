import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord
from wom import NameChangeStatus

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    mock_require_role,
    create_mock_discord_interaction,
    create_test_member,
)

with patch("ironforgedbot.decorators.decorators.require_role", mock_require_role):
    from ironforgedbot.commands.lookup.cmd_whois import cmd_whois


class TestCmdWhois(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)
        self.mock_member = self.mock_interaction.user

        self.mock_name_change = Mock()
        self.mock_name_change.new_name = "NewName"
        self.mock_name_change.old_name = "OldName"
        self.mock_name_change.status = NameChangeStatus.Approved
        self.mock_name_change.resolved_at = "2023-01-01T00:00:00Z"

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.get_wom_service")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_with_name_changes(
        self,
        mock_validate_playername,
        mock_get_wom_service,
        mock_render_time,
        mock_build_embed,
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_name_history.return_value = [self.mock_name_change]
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service
        mock_render_time.return_value = "2 days ago"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_validate_playername.assert_called_once_with(
            self.mock_interaction.guild, "TestPlayer", must_be_member=False
        )
        mock_wom_service.get_player_name_history.assert_called_once_with("TestPlayer")
        mock_build_embed.assert_called_once_with(
            "📋 TestPlayer | Name History", "", discord.Colour.purple()
        )
        mock_embed.add_field.assert_called_once_with(
            name="", value="**2 days ago**: OldName → NewName", inline=False
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.get_wom_service")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_no_name_changes(
        self, mock_validate_playername, mock_get_wom_service, mock_build_embed
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_name_history.return_value = []
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_embed.add_field.assert_called_once_with(
            name="", value="No name changes found for this user.", inline=False
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.text_bold")
    @patch("ironforgedbot.commands.lookup.cmd_whois.get_wom_service")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_many_name_changes_truncated(
        self,
        mock_validate_playername,
        mock_get_wom_service,
        mock_text_bold,
        mock_render_time,
        mock_build_embed,
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")

        # Create 30 name changes to trigger truncation at 24
        name_changes = []
        for i in range(30):
            name_change = Mock()
            name_change.new_name = f"NewName{i}"
            name_change.old_name = f"OldName{i}"
            name_change.status = NameChangeStatus.Approved
            name_change.resolved_at = "2023-01-01T00:00:00Z"
            name_changes.append(name_change)

        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_name_history.return_value = name_changes
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service
        mock_render_time.return_value = "2 days ago"
        mock_text_bold.side_effect = lambda x: f"**{x}**"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_whois(self.mock_interaction, "TestPlayer")

        # Should be called 25 times: 24 name changes + 1 truncation message
        self.assertEqual(mock_embed.add_field.call_count, 25)

        # Check that truncation message is added
        last_call = mock_embed.add_field.call_args_list[-1]
        self.assertIn("...and **6** more not shown.", last_call[1]["value"])

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.get_wom_service")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_filters_non_approved_changes(
        self,
        mock_validate_playername,
        mock_get_wom_service,
        mock_render_time,
        mock_build_embed,
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")

        # Create approved and non-approved name changes
        approved_change = Mock()
        approved_change.new_name = "ApprovedName"
        approved_change.old_name = "OldName"
        approved_change.status = NameChangeStatus.Approved
        approved_change.resolved_at = "2023-01-01T00:00:00Z"

        denied_change = Mock()
        denied_change.new_name = "DeniedName"
        denied_change.old_name = "OldName"
        denied_change.status = NameChangeStatus.Denied
        denied_change.resolved_at = "2023-01-01T00:00:00Z"

        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_name_history.return_value = [
            approved_change,
            denied_change,
        ]
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service
        mock_render_time.return_value = "2 days ago"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_whois(self.mock_interaction, "TestPlayer")

        # Should only add field for approved change, not denied one
        mock_embed.add_field.assert_called_once_with(
            name="", value="**2 days ago**: OldName → ApprovedName", inline=False
        )

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.get_wom_service")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_wom_service_error(
        self, mock_validate_playername, mock_get_wom_service, mock_send_error
    ):
        from ironforgedbot.services.wom_service import WomServiceError

        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_name_history.side_effect = WomServiceError(
            "API error"
        )
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_send_error.assert_called_once_with(
            self.mock_interaction,
            "Error getting name change history",
            report_to_channel=False,
        )

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.get_wom_service")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_rate_limit_error(
        self, mock_validate_playername, mock_get_wom_service, mock_send_error
    ):
        from ironforgedbot.services.wom_service import WomRateLimitError

        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_name_history.side_effect = WomRateLimitError(
            "Rate limit"
        )
        mock_get_wom_service.return_value.__aenter__.return_value = mock_wom_service

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_send_error.assert_called_once_with(
            self.mock_interaction,
            "WOM API rate limit exceeded. Please try again later.",
            report_to_channel=False,
        )

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_validate_player_error(
        self, mock_validate_playername, mock_send_error
    ):
        mock_validate_playername.side_effect = Exception("Invalid player")

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_send_error.assert_called_once_with(
            self.mock_interaction, "Invalid player", report_to_channel=False
        )
