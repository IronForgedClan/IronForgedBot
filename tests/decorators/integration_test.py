import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.require_channel import require_channel
from ironforgedbot.decorators.require_role import require_role
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestDecoratorIntegration(unittest.IsolatedAsyncioTestCase):
    """Test that decorators integrate properly and work together."""

    async def test_require_role_decorator_preserves_function_metadata(self):
        """Test that require_role preserves function metadata via functools.wraps"""

        async def test_func():
            """Test docstring"""
            pass

        decorated_func = require_role(ROLE.MEMBER)(test_func)

        # Verify that functools.wraps preserved metadata
        self.assertTrue(hasattr(decorated_func, "__wrapped__"))
        self.assertEqual(decorated_func.__doc__, "Test docstring")

    async def test_require_channel_decorator_preserves_function_metadata(self):
        """Test that require_channel preserves function metadata via functools.wraps"""

        async def test_func():
            """Test docstring"""
            pass

        decorated_func = require_channel([123, 456])(test_func)

        # Verify that functools.wraps preserved metadata
        self.assertTrue(hasattr(decorated_func, "__wrapped__"))
        self.assertEqual(decorated_func.__doc__, "Test docstring")

    async def test_check_member_has_role_logic(self):
        """Test the core role checking logic"""
        from ironforgedbot.common.roles import check_member_has_role

        # User with Member role should have access to Member commands
        member_user = create_test_member("member", [ROLE.MEMBER])
        self.assertTrue(check_member_has_role(member_user, ROLE.MEMBER, or_higher=True))

        # User with Member role should NOT have access to Leadership commands
        self.assertFalse(
            check_member_has_role(member_user, ROLE.LEADERSHIP, or_higher=True)
        )

        # User with Leadership role SHOULD have access to Member commands (or_higher)
        leader_user = create_test_member("leader", [ROLE.LEADERSHIP])
        self.assertTrue(check_member_has_role(leader_user, ROLE.MEMBER, or_higher=True))

    async def test_rate_limit_still_returns_result(self):
        """Test that rate_limit decorator preserves return values"""
        from ironforgedbot.decorators.rate_limit import rate_limit

        expected_result = "test_result"

        async def test_func(interaction):
            return expected_result

        mock_func = AsyncMock(wraps=test_func)
        mock_interaction = create_mock_discord_interaction()
        mock_interaction.command = Mock()
        mock_interaction.command.name = "test_command"

        with patch("ironforgedbot.decorators.rate_limit.STATE") as mock_state:
            mock_state.state = {"rate_limit": {}}
            decorated_func = rate_limit(1, 3600)(mock_func)
            result = await decorated_func(mock_interaction)

            self.assertEqual(result, expected_result)

    @patch("ironforgedbot.decorators.require_role.STATE")
    async def test_stacked_decorators_role_pass_channel_fail(self, mock_state):
        """Test that stacked decorators don't defer multiple times when channel check fails"""
        from ironforgedbot.decorators.rate_limit import rate_limit

        mock_state.state = {"rate_limit": {}, "is_shutting_down": False}

        mock_func = AsyncMock(return_value="success")
        mock_member = create_test_member("tester", [ROLE.MEMBER])
        mock_interaction = create_mock_discord_interaction(
            user=mock_member, channel_id=999
        )
        mock_interaction.guild.get_member.return_value = mock_member
        mock_interaction.command = Mock()
        mock_interaction.command.name = "test_command"

        # Set up is_done to track defer calls properly
        defer_count = [0]

        def track_defer(*args, **kwargs):
            defer_count[0] += 1

        def is_done_check():
            return defer_count[0] > 0

        mock_interaction.response.defer.side_effect = track_defer
        mock_interaction.response.is_done.side_effect = is_done_check

        # Stack decorators like in production
        @require_role(ROLE.MEMBER)
        @require_channel([123, 456])
        async def test_command(interaction):
            return await mock_func(interaction)

        result = await test_command(mock_interaction)

        # Should defer exactly once (by require_role, then safe_defer in require_channel is a no-op)
        self.assertEqual(mock_interaction.response.defer.call_count, 1)
        # Function should not be called since channel check failed
        mock_func.assert_not_called()

    @patch("ironforgedbot.decorators.rate_limit.STATE")
    async def test_stacked_decorators_role_channel_pass_rate_limit_fail(
        self, mock_state
    ):
        """Test that stacked decorators don't defer multiple times when rate limit hits"""
        from ironforgedbot.decorators.rate_limit import rate_limit

        mock_state.state = {"rate_limit": {}, "is_shutting_down": False}

        mock_func = AsyncMock(return_value="success")
        mock_member = create_test_member("tester", [ROLE.MEMBER])
        mock_interaction = create_mock_discord_interaction(
            user=mock_member, channel_id=123
        )
        mock_interaction.guild.get_member.return_value = mock_member
        mock_interaction.command = Mock()
        mock_interaction.command.name = "test_command"

        # Set up is_done to track defer calls properly
        defer_count = [0]

        def track_defer(*args, **kwargs):
            defer_count[0] += 1

        def is_done_check():
            return defer_count[0] > 0

        mock_interaction.response.defer.side_effect = track_defer
        mock_interaction.response.is_done.side_effect = is_done_check

        # Simulate rate limit already hit
        mock_state.state["rate_limit"]["test_command"] = {
            str(mock_interaction.user.id): [time.time()]
        }

        # Stack decorators like in production
        @require_role(ROLE.MEMBER)
        @require_channel([123, 456])
        @rate_limit(1, 3600)
        async def test_command(interaction):
            return await mock_func(interaction)

        result = await test_command(mock_interaction)

        # Should defer exactly once (by require_role, then safe_defer in rate_limit is a no-op)
        self.assertEqual(mock_interaction.response.defer.call_count, 1)
        # Function should not be called since rate limit hit
        mock_func.assert_not_called()

    @patch("ironforgedbot.decorators.rate_limit.STATE")
    async def test_stacked_decorators_all_pass(self, mock_state):
        """Test that stacked decorators work correctly when all checks pass"""
        from ironforgedbot.decorators.rate_limit import rate_limit

        mock_state.state = {"rate_limit": {}, "is_shutting_down": False}

        expected_result = "success"
        mock_func = AsyncMock(return_value=expected_result)
        mock_member = create_test_member("tester", [ROLE.MEMBER])
        mock_interaction = create_mock_discord_interaction(
            user=mock_member, channel_id=123
        )
        mock_interaction.guild.get_member.return_value = mock_member
        mock_interaction.command = Mock()
        mock_interaction.command.name = "test_command"

        # Set up is_done to track defer calls properly
        defer_count = [0]

        def track_defer(*args, **kwargs):
            defer_count[0] += 1

        def is_done_check():
            return defer_count[0] > 0

        mock_interaction.response.defer.side_effect = track_defer
        mock_interaction.response.is_done.side_effect = is_done_check

        # Stack decorators like in production
        @require_role(ROLE.MEMBER)
        @require_channel([123, 456])
        @rate_limit(1, 3600)
        async def test_command(interaction):
            return await mock_func(interaction)

        result = await test_command(mock_interaction)

        # Should defer exactly once (by require_role)
        self.assertEqual(mock_interaction.response.defer.call_count, 1)
        # Function should be called since all checks passed
        mock_func.assert_called_once_with(mock_interaction)
        # Should return the expected result
        self.assertEqual(result, expected_result)
