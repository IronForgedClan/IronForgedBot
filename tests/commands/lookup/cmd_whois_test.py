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

with patch("ironforgedbot.decorators.require_role", mock_require_role):
    from ironforgedbot.commands.lookup.cmd_whois import cmd_whois


class TestCmdWhois(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)
        self.mock_member = self.mock_interaction.user

        self.mock_wom_client = AsyncMock()
        self.mock_wom_client.start = AsyncMock()
        self.mock_wom_client.close = AsyncMock()
        self.mock_wom_client.players.get_name_changes = AsyncMock()

        self.mock_name_change = Mock()
        self.mock_name_change.new_name = "NewName"
        self.mock_name_change.old_name = "OldName"
        self.mock_name_change.status = NameChangeStatus.Approved
        self.mock_name_change.resolved_at = "2023-01-01T00:00:00Z"

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_with_name_changes(
        self, mock_validate_playername, mock_client, mock_render_time, mock_build_embed
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client
        mock_render_time.return_value = "2 days ago"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        mock_result = Mock()
        mock_result.is_err = False
        mock_result.unwrap.return_value = [self.mock_name_change]
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_validate_playername.assert_called_once_with(
            self.mock_interaction.guild, "TestPlayer", must_be_member=False
        )
        self.mock_wom_client.start.assert_called_once()
        self.mock_wom_client.players.get_name_changes.assert_called_once_with(
            "TestPlayer"
        )
        mock_build_embed.assert_called_once_with(
            "📋 TestPlayer | Name History", "", discord.Colour.purple()
        )
        mock_embed.add_field.assert_called_once_with(
            name="", value="**2 days ago**: OldName → NewName", inline=False
        )
        self.mock_wom_client.close.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_no_name_changes(
        self, mock_validate_playername, mock_client, mock_build_embed
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        mock_result = Mock()
        mock_result.is_err = False
        mock_result.unwrap.return_value = []
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_embed.add_field.assert_called_once_with(
            name="", value="No name changes found for this user.", inline=False
        )
        self.mock_wom_client.close.assert_called_once()
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_non_member_player(
        self, mock_validate_playername, mock_client, mock_render_time, mock_build_embed
    ):
        mock_validate_playername.return_value = (None, "NonMemberPlayer")
        mock_client.return_value = self.mock_wom_client
        mock_render_time.return_value = "1 week ago"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        mock_result = Mock()
        mock_result.is_err = False
        mock_result.unwrap.return_value = [self.mock_name_change]
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "NonMemberPlayer")

        mock_build_embed.assert_called_once_with(
            "📋 NonMemberPlayer | Name History", "", discord.Colour.purple()
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.text_bold")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_pending_name_change(
        self,
        mock_validate_playername,
        mock_client,
        mock_text_bold,
        mock_render_time,
        mock_build_embed,
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client
        mock_text_bold.side_effect = ["**pending**", "****pending****"]

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        pending_change = Mock()
        pending_change.new_name = "PendingName"
        pending_change.old_name = "CurrentName"
        pending_change.status = NameChangeStatus.Approved
        pending_change.resolved_at = None

        mock_result = Mock()
        mock_result.is_err = False
        mock_result.unwrap.return_value = [pending_change]
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "TestPlayer")

        from unittest.mock import call

        expected_calls = [call("pending"), call("**pending**")]
        mock_text_bold.assert_has_calls(expected_calls)
        mock_embed.add_field.assert_called_once_with(
            name="", value="****pending****: CurrentName → PendingName", inline=False
        )

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.text_bold")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_success_many_name_changes_truncated(
        self,
        mock_validate_playername,
        mock_client,
        mock_text_bold,
        mock_render_time,
        mock_build_embed,
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client
        mock_render_time.return_value = "1 day ago"
        mock_text_bold.return_value = "**26**"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

        name_changes = []
        for i in range(26):
            change = Mock()
            change.new_name = f"Name{i}"
            change.old_name = f"OldName{i}"
            change.status = NameChangeStatus.Approved
            change.resolved_at = "2023-01-01T00:00:00Z"
            name_changes.append(change)

        mock_result = Mock()
        mock_result.is_err = False
        mock_result.unwrap.return_value = name_changes
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "TestPlayer")

        self.assertEqual(mock_embed.add_field.call_count, 25)
        last_call_args = mock_embed.add_field.call_args_list[-1]
        self.assertIn("...and **26** more not shown.", last_call_args[1]["value"])

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_validation_error(
        self, mock_validate_playername, mock_send_error_response
    ):
        mock_validate_playername.side_effect = ValueError("Invalid player name")

        await cmd_whois(self.mock_interaction, "InvalidPlayer")

        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Invalid player name", report_to_channel=False
        )

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_wom_client_connection_error(
        self, mock_validate_playername, mock_client, mock_send_error_response
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client
        self.mock_wom_client.start.side_effect = Exception("Connection failed")

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Error connecting to api"
        )

    @patch("ironforgedbot.commands.lookup.cmd_whois.send_error_response")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_wom_api_error(
        self, mock_validate_playername, mock_client, mock_send_error_response
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client

        mock_result = Mock()
        mock_result.is_err = True
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_send_error_response.assert_called_once_with(
            self.mock_interaction, "Error getting name change history", report_to_channel=False
        )
        self.mock_wom_client.close.assert_called_once()

    @patch("ironforgedbot.commands.lookup.cmd_whois.build_response_embed")
    @patch("ironforgedbot.commands.lookup.cmd_whois.render_relative_time")
    @patch("ironforgedbot.commands.lookup.cmd_whois.Client")
    @patch("ironforgedbot.commands.lookup.cmd_whois.validate_playername")
    async def test_cmd_whois_filters_non_approved_changes(
        self, mock_validate_playername, mock_client, mock_render_time, mock_build_embed
    ):
        mock_validate_playername.return_value = (self.mock_member, "TestPlayer")
        mock_client.return_value = self.mock_wom_client
        mock_render_time.return_value = "1 day ago"

        mock_embed = Mock()
        mock_embed.add_field = Mock()
        mock_build_embed.return_value = mock_embed

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

        mock_result = Mock()
        mock_result.is_err = False
        mock_result.unwrap.return_value = [approved_change, denied_change]
        self.mock_wom_client.players.get_name_changes.return_value = mock_result

        await cmd_whois(self.mock_interaction, "TestPlayer")

        mock_embed.add_field.assert_called_once_with(
            name="", value="**1 day ago**: OldName → ApprovedName", inline=False
        )
