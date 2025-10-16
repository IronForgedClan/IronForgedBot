import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.decorators import (
    require_channel,
    require_role,
    retry_on_exception,
    singleton,
)
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

        # Set guild.get_member return value (None means member not found)
        if guild_member_return == "default":
            guild_member_return = mock_member
        mock_interaction.guild.get_member.return_value = guild_member_return

        return mock_func, mock_member, mock_interaction

    async def test_require_role(self):
        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.LEADERSHIP]
        )

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)
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
        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        with self.assertRaises(ReferenceError) as context:
            await decorated_func("")

        self.assertEqual(
            str(context.exception),
            f"Expected discord.Interaction as first argument ({mock_func.__name__})",
        )

    async def test_require_role_fail_unable_to_find_member(self):
        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.LEADERSHIP], guild_member_return=None
        )

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        with self.assertRaises(ValueError) as context:
            await decorated_func(mock_interaction)

        self.assertEqual(
            str(context.exception),
            f"Unable to verify caller's guild membership ({mock_func.__name__})",
        )

    async def test_require_role_user_does_not_have_role(self):
        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.MEMBER]
        )

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)

        with self.assertRaises(discord.app_commands.CheckFailure) as context:
            await decorated_func(mock_interaction)

        self.assertEqual(
            str(context.exception),
            f"Member '{mock_member.display_name}' tried using '{mock_func.__name__}' but does not have permission",
        )

    @patch("ironforgedbot.decorators.decorators.STATE")
    async def test_require_role_ignore_command_if_shutting_down(self, mock_state):
        mock_state.state["is_shutting_down"].return_value = True

        mock_func, mock_member, mock_interaction = self.create_role_test_setup(
            [ROLE.MEMBER]
        )
        mock_interaction.response.send_message = AsyncMock()

        decorated_func = require_role(ROLE.LEADERSHIP)(mock_func)
        await decorated_func(mock_interaction)

        mock_func.assert_not_awaited()
        mock_interaction.response.send_message.assert_called_with(
            "## Bad Timing!!\nThe bot is shutting down, please try again when the bot comes back online."
        )


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

    @patch("ironforgedbot.decorators.decorators.logger", new_callable=MagicMock)
    @patch("asyncio.sleep", return_value=None)
    async def test_retry_on_exception_retries(self, mock_sleep, mock_logger):
        func = self.create_retry_func(fail_count=2, success_msg="Success!")

        decorated_func = retry_on_exception(3)(func)
        result = await decorated_func()

        self.assertEqual(result, "Success!")
        self.assertEqual(func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_logger.warning.assert_called()

    @patch("ironforgedbot.decorators.decorators.logger", new_callable=MagicMock)
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

    async def test_require_channel(self):
        mock_func, mock_interaction, allowed_channels = self.create_channel_test_setup()

        decorated_func = require_channel(allowed_channels)(mock_func)
        await decorated_func(mock_interaction)

        mock_func.assert_awaited_once()

    async def test_require_channel_fails_interaction_not_first_arg(self):
        mock_func = AsyncMock()
        decorated_func = require_channel([12345])(mock_func)

        with self.assertRaises(ReferenceError) as context:
            await decorated_func("")

        self.assertEqual(
            str(context.exception),
            f"Expected discord.Interaction as first argument ({mock_func.__name__})",
        )

    @patch("ironforgedbot.common.responses.send_error_response")
    async def test_require_channel_fails_invalid_channel_id(
        self, mock_send_error_response
    ):
        mock_func, mock_interaction, _ = self.create_channel_test_setup(
            channel_id=123, allowed_channels=[12345, 54321]
        )
        decorated_func = require_channel([12345, 54321])(mock_func)

        await decorated_func(mock_interaction)

        mock_send_error_response.assert_awaited_once()
        mock_func.assert_not_awaited()


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
