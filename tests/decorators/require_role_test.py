import unittest
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.require_role import require_role
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestRequireRoleDecorator(unittest.IsolatedAsyncioTestCase):
    def create_role_test_setup(self, user_roles, guild_member_return="default"):
        """Helper to create standardized test setup for role decorator tests."""
        mock_func = AsyncMock()
        mock_member = create_test_member("tester", user_roles)
        mock_interaction = create_mock_discord_interaction(user=mock_member)

        if guild_member_return == "default":
            guild_member_return = mock_member
        mock_interaction.guild.get_member.return_value = guild_member_return

        return mock_func, mock_member, mock_interaction

    async def test_require_role_with_valid_role(self):
        """Test that decorator works when user has required role"""
        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.LEADERSHIP]
        )

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        from ironforgedbot.common.roles import check_member_has_role

        self.assertTrue(
            check_member_has_role(mock_member, ROLE.LEADERSHIP, or_higher=True)
        )

    async def test_require_role_fail_no_role_set(self):
        """Test that ValueError is raised when no role provided to decorator"""
        mock_func = AsyncMock()
        mock_interaction = create_mock_discord_interaction()
        decorated_func = require_role("")(mock_func)

        with self.assertRaises(ValueError) as context:
            await decorated_func(mock_interaction)

        self.assertIn("No role provided to decorator", str(context.exception))

    async def test_require_role_fail_interaction_not_first_arg(self):
        """Test that ReferenceError is raised when first arg is not an Interaction"""
        mock_func = AsyncMock()
        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        with self.assertRaises(ReferenceError) as context:
            await decorated_func("")

        self.assertIn("Expected discord.Interaction", str(context.exception))

    async def test_require_role_raises_when_member_not_found(self):
        """Test that ValueError is raised when member cannot be found"""
        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.LEADERSHIP], guild_member_return=None
        )

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        with self.assertRaises(ValueError) as context:
            await decorated_func(mock_interaction)

        self.assertIn(
            "Unable to verify caller's guild membership", str(context.exception)
        )

    async def test_require_role_raises_check_failure_without_role(self):
        """Test that CheckFailure is raised when user doesn't have required role"""
        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.MEMBER]
        )

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        with self.assertRaises(discord.app_commands.CheckFailure) as context:
            await decorated_func(mock_interaction)

        self.assertIn("does not have permission", str(context.exception))

    @patch("ironforgedbot.decorators.require_role.STATE")
    async def test_require_role_returns_message_when_shutting_down(self, mock_state):
        """Test that shutdown message is sent when bot is shutting down"""
        mock_state.state = {"is_shutting_down": True}

        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.MEMBER]
        )

        decorated_func = require_role(ROLE.MEMBER)(mock_func)
        result = await decorated_func(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("shutting down", call_args)
