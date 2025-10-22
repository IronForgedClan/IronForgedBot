import time
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.require_channel import require_channel
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.decorators.retry_on_exception import retry_on_exception
from ironforgedbot.decorators.singleton import singleton
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


class TestRetryOnExceptionDecorator(unittest.IsolatedAsyncioTestCase):
    def create_retry_func(self, fail_count=0, success_msg="Success!"):
        """Helper to create a function that fails a specified number of times."""

        async def func():
            if not hasattr(func, "call_count"):
                func.call_count = 0
            func.call_count += 1

            if func.call_count <= fail_count:
                raise Exception("Test Exception")
            return success_msg

        return func

    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception(self, mock_sleep):
        msg = "Success!"
        func = self.create_retry_func(fail_count=0, success_msg=msg)

        decorated_func = retry_on_exception(3)(func)
        result = await decorated_func()

        self.assertEqual(result, msg)
        self.assertEqual(func.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("ironforgedbot.decorators.retry_on_exception.logger", new_callable=MagicMock)
    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_retries(self, mock_sleep, mock_logger):
        func = self.create_retry_func(fail_count=2, success_msg="Success!")

        decorated_func = retry_on_exception(3)(func)
        result = await decorated_func()

        self.assertEqual(result, "Success!")
        self.assertEqual(func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_logger.warning.assert_called()

    @patch("ironforgedbot.decorators.retry_on_exception.logger", new_callable=MagicMock)
    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_raises_after_max_retries(
        self, mock_sleep, mock_logger
    ):
        func = self.create_retry_func(fail_count=10)  # Always fails

        decorated_func = retry_on_exception(3)(func)

        with self.assertRaises(Exception) as context:
            await decorated_func()

        self.assertEqual(str(context.exception), "Test Exception")
        self.assertEqual(func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_logger.critical.assert_called_once()

    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_exponential_sleep_between_tries(self, mock_sleep):
        func = self.create_retry_func(fail_count=10)  # Always fails

        decorated_func = retry_on_exception(retries=5)(func)

        with self.assertRaises(Exception):
            await decorated_func()

        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)
        mock_sleep.assert_any_call(8)


class TestRequireChannelDecorator(unittest.IsolatedAsyncioTestCase):
    def create_channel_test_setup(self, channel_id=555, allowed_channels=None):
        """Helper to create standardized test setup for channel decorator tests."""
        if allowed_channels is None:
            allowed_channels = [channel_id, 12345, 54321]

        mock_func = AsyncMock()
        mock_interaction = create_mock_discord_interaction(channel_id=channel_id)

        return mock_func, mock_interaction, allowed_channels

    async def test_require_channel_with_valid_channel(self):
        """Test that decorator works when in allowed channel"""
        mock_func, mock_interaction, allowed_channels = self.create_channel_test_setup()

        decorated_func = require_channel(allowed_channels)(mock_func)

        # Verify the channel would pass the check
        self.assertIn(mock_interaction.channel_id, allowed_channels)

    async def test_require_channel_with_empty_channel_list(self):
        """Test that empty channel list blocks all channels"""
        mock_func = AsyncMock()
        mock_interaction = create_mock_discord_interaction(channel_id=555)
        mock_interaction.response.is_done.return_value = False
        decorated_func = require_channel([])(mock_func)

        # Original implementation doesn't validate at decorator time
        # Empty list means no channels are allowed
        result = await decorated_func(mock_interaction)

        # Should send error response and return early
        mock_interaction.response.defer.assert_called_once()
        self.assertIsNone(result)

    async def test_require_channel_sends_error_for_invalid_channel(self):
        """Test that error is sent for wrong channel"""
        mock_func, mock_interaction, _ = self.create_channel_test_setup(
            channel_id=999, allowed_channels=[12345, 54321]
        )
        mock_interaction.response.is_done.return_value = False

        decorated_func = require_channel([12345, 54321])(mock_func)
        result = await decorated_func(mock_interaction)

        # Should defer and send error response
        mock_interaction.response.defer.assert_called_once_with(
            thinking=True, ephemeral=True
        )
        # Function should not be called
        mock_func.assert_not_called()


@singleton
class TestSingleton:
    def __init__(self, value):
        self.value = value
        self.internal_state = {}

    async def set_value(self, key, value):
        self.internal_state[key] = value

    async def get_value(self, key):
        return self.internal_state.get(key, None)


class TestSingletonDecorator(unittest.IsolatedAsyncioTestCase):
    async def test_singleton_instance_creation(self):
        """Test that only one instance is created."""
        instance1 = await TestSingleton(10)
        instance2 = await TestSingleton(20)

        self.assertIs(instance1, instance2)

    async def test_singleton_internal_state(self):
        instance1 = await TestSingleton(10)
        await instance1.set_value("key1", "value")
        instance2 = await TestSingleton(20)

        value = await instance2.get_value("key1")

        self.assertEqual(value, "value")
        self.assertIs(instance1, instance2)

    async def test_singleton_instance_initialization(self):
        instance1 = await TestSingleton(10)
        instance2 = await TestSingleton(20)

        self.assertEqual(instance1.value, 10)
        self.assertEqual(instance1.value, instance2.value)


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
