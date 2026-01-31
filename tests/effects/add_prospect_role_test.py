import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE, PROSPECT_ROLE_NAME
from ironforgedbot.effects.add_prospect_role import add_prospect_role
from tests.helpers import create_test_member


class AddProspectRoleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_report_channel.guild = self.mock_guild
        self.member = create_test_member("TestUser", [PROSPECT_ROLE_NAME], "TestUser")
        self.member.id = 123456789
        self.member.display_name = "TestUser"
        self.member.mention = "<@123456789>"
        self.member.add_roles = AsyncMock()
        self.member.remove_roles = AsyncMock()

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_adds_prospect_role_without_other_changes(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_get_role.return_value = mock_prospect_role
        mock_check_role.side_effect = lambda member, role: False
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            await add_prospect_role(self.mock_report_channel, self.member)

        self.mock_report_channel.send.assert_called_once()
        call_args = self.mock_report_channel.send.call_args[0][0]
        self.assertIn("given the **Prospect** role", call_args)
        mock_message.edit.assert_called_once()

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_removes_applicant_role_when_present(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_applicant_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.APPLICANT: mock_applicant_role,
            ROLE.GUEST: Mock(),
            ROLE.MEMBER: Mock(),
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role == ROLE.APPLICANT
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            await add_prospect_role(self.mock_report_channel, self.member)

        self.member.remove_roles.assert_called_once_with(
            mock_applicant_role, reason="Prospect: remove Applicant role"
        )
        mock_message.edit.assert_called_once()
        edit_content = mock_message.edit.call_args[1]["content"]
        self.assertIn("Removed roles:  **Applicant**", edit_content)

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_removes_guest_role_when_present(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_guest_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.APPLICANT: Mock(),
            ROLE.GUEST: mock_guest_role,
            ROLE.MEMBER: Mock(),
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role == ROLE.GUEST
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            await add_prospect_role(self.mock_report_channel, self.member)

        self.member.remove_roles.assert_called_once_with(
            mock_guest_role, reason="Prospect: remove Guest role"
        )
        mock_message.edit.assert_called_once()
        edit_content = mock_message.edit.call_args[1]["content"]
        self.assertIn("Removed roles:  **Guest**", edit_content)

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_adds_member_role_when_missing(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_member_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.APPLICANT: Mock(),
            ROLE.GUEST: Mock(),
            ROLE.MEMBER: mock_member_role,
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role != ROLE.MEMBER
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            await add_prospect_role(self.mock_report_channel, self.member)

        self.member.add_roles.assert_called_once_with(
            mock_member_role, reason="Prospect: adding Member role"
        )
        mock_message.edit.assert_called_once()
        edit_content = mock_message.edit.call_args[1]["content"]
        self.assertIn("Added roles:  **Member**", edit_content)

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_handles_multiple_role_changes(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_applicant_role = Mock()
        mock_guest_role = Mock()
        mock_member_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.APPLICANT: mock_applicant_role,
            ROLE.GUEST: mock_guest_role,
            ROLE.MEMBER: mock_member_role,
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role in [
            ROLE.APPLICANT,
            ROLE.GUEST,
        ]
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            await add_prospect_role(self.mock_report_channel, self.member)

        self.member.remove_roles.assert_any_call(
            mock_applicant_role, reason="Prospect: remove Applicant role"
        )
        self.member.remove_roles.assert_any_call(
            mock_guest_role, reason="Prospect: remove Guest role"
        )
        self.member.add_roles.assert_called_once_with(
            mock_member_role, reason="Prospect: adding Member role"
        )
        mock_message.edit.assert_called_once()
        edit_content = mock_message.edit.call_args[1]["content"]
        self.assertIn("Added roles:  **Member**", edit_content)
        self.assertIn("Removed roles:  **Applicant**, **Guest**", edit_content)

    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    async def test_raises_error_when_prospect_role_not_found(self, mock_get_role):
        mock_get_role.return_value = None
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        with self.assertRaises(ValueError) as context:
            await add_prospect_role(self.mock_report_channel, self.member)

        self.assertEqual(str(context.exception), "Unable to access Prospect role value")

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_raises_error_when_applicant_role_not_found(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.APPLICANT: None,
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role == ROLE.APPLICANT
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            with self.assertRaises(ValueError) as context:
                await add_prospect_role(self.mock_report_channel, self.member)

        self.assertEqual(
            str(context.exception), "Unable to access Applicant role values"
        )

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_raises_error_when_guest_role_not_found(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.GUEST: None,
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role == ROLE.GUEST
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            with self.assertRaises(ValueError) as context:
                await add_prospect_role(self.mock_report_channel, self.member)

        self.assertEqual(str(context.exception), "Unable to access Guest role values")

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_raises_error_when_member_role_not_found(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_get_role.side_effect = lambda guild, role: {
            PROSPECT_ROLE_NAME: mock_prospect_role,
            ROLE.APPLICANT: Mock(),
            ROLE.GUEST: Mock(),
            ROLE.MEMBER: None,
        }.get(role)
        mock_check_role.side_effect = lambda member, role: role != ROLE.MEMBER
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            with self.assertRaises(ValueError) as context:
                await add_prospect_role(self.mock_report_channel, self.member)

        self.assertEqual(str(context.exception), "Unable to access Member role value")

    @patch("ironforgedbot.effects.add_prospect_role.db")
    @patch("ironforgedbot.effects.add_prospect_role.find_emoji")
    @patch("ironforgedbot.effects.add_prospect_role.get_discord_role")
    @patch("ironforgedbot.effects.add_prospect_role.check_member_has_role")
    async def test_updates_is_prospect_flag_in_database(
        self, mock_check_role, mock_get_role, mock_emoji, mock_db
    ):
        mock_emoji.return_value = "🔍"
        mock_prospect_role = Mock()
        mock_get_role.return_value = mock_prospect_role
        mock_check_role.side_effect = lambda member, role: False
        mock_message = Mock()
        mock_message.edit = AsyncMock()
        self.mock_report_channel.send.return_value = mock_message

        # Setup database mock
        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session
        mock_service = Mock()
        mock_db_member = Mock()
        mock_db_member.id = "test-id"
        mock_service.get_member_by_discord_id = AsyncMock(return_value=mock_db_member)
        mock_service.update_member_flags = AsyncMock()

        with patch(
            "ironforgedbot.effects.add_prospect_role.MemberService",
            return_value=mock_service,
        ):
            await add_prospect_role(self.mock_report_channel, self.member)

        mock_service.update_member_flags.assert_called_once_with(
            mock_db_member.id, is_prospect=True
        )
