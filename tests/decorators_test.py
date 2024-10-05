import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role
from tests.helpers import create_mock_discord_interaction, create_test_member


class TestRequireRoleDecorator(unittest.IsolatedAsyncioTestCase):
    async def test_require_role(self):
        mock_func = AsyncMock()

        mock_member = create_test_member("tester", ROLES.LEADERSHIP)
        mock_interaction = create_mock_discord_interaction()

        mock_guild = Mock(spec=discord.Guild)
        mock_guild.get_member.return_value = mock_member

        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_member

        decorated_func = require_role(ROLES.LEADERSHIP)(mock_func)
        await decorated_func(mock_interaction)

        mock_func.assert_awaited_once()

    async def test_require_role_fail_no_role_set(self):
        mock_func = AsyncMock()
        mock_interaction = create_mock_discord_interaction()
        decorated_func = require_role("")(mock_func)

        with self.assertRaises(ValueError) as context:
            await decorated_func(mock_interaction)

        self.assertEqual(
            str(context.exception),
            f"No role provided to decorator ({mock_func.__name__})",
        )

    async def test_require_role_fail_interaction_not_first_arg(self):
        mock_func = AsyncMock()
        decorated_func = require_role(ROLES.LEADERSHIP)(mock_func)

        with self.assertRaises(ReferenceError) as context:
            await decorated_func("")

        self.assertEqual(
            str(context.exception),
            f"Expected discord.Interaction as first argument ({mock_func.__name__})",
        )

    async def test_require_role_fail_unable_to_find_member(self):
        mock_func = AsyncMock()

        mock_member = create_test_member("tester", ROLES.LEADERSHIP)
        mock_interaction = Mock(spec=discord.Interaction)

        mock_guild = Mock(spec=discord.Guild)
        mock_guild.get_member.return_value = None

        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_member

        decorated_func = require_role(ROLES.LEADERSHIP)(mock_func)

        with self.assertRaises(ValueError) as context:
            await decorated_func(mock_interaction)

        self.assertEqual(
            str(context.exception),
            f"Unable to verify caller's guild membership ({mock_func.__name__})",
        )

    async def test_require_role_user_does_not_have_role(self):
        mock_func = AsyncMock()

        mock_member = create_test_member("tester", ROLES.MEMBER)
        mock_interaction = Mock(spec=discord.Interaction)

        mock_guild = Mock(spec=discord.Guild)
        mock_guild.get_member.return_value = mock_member

        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_member

        decorated_func = require_role(ROLES.LEADERSHIP)(mock_func)

        with self.assertRaises(discord.app_commands.CheckFailure) as context:
            await decorated_func(mock_interaction)

        self.assertEqual(
            str(context.exception),
            f"Member '{mock_member.display_name}' tried using {mock_func.__name__} but does not have permission",
        )

    @patch("ironforgedbot.decorators.state")
    async def test_ignore_command_if_shutting_down(self, mock_state):
        mock_state.is_shutting_down.return_value = True

        mock_func = AsyncMock()

        mock_member = create_test_member("tester", ROLES.MEMBER)
        mock_interaction = Mock(spec=discord.Interaction)

        mock_guild = Mock(spec=discord.Guild)
        mock_guild.get_member.return_value = mock_member

        mock_interaction.guild = mock_guild
        mock_interaction.user = mock_member
        mock_interaction.response.send_message = AsyncMock()

        decorated_func = require_role(ROLES.LEADERSHIP)(mock_func)
        await decorated_func(mock_interaction)

        mock_func.assert_not_awaited()
        mock_interaction.response.send_message.assert_called_with(
            "## Bad Timing!!\nThe bot is shutting down, please try again when the bot comes back online."
        )
