import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.events.member_events import HandlerResult, MemberUpdateContext
from ironforgedbot.events.member_update_emitter import MemberUpdateEmitter
from tests.helpers import create_mock_discord_role, create_test_member


class TestMemberUpdateEmitter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.emitter = MemberUpdateEmitter()
        self.before = create_test_member("TestUser", ["Member"], "TestNick")
        self.after = create_test_member("TestUser", ["Member"], "TestNick")
        self.after.id = self.before.id
        self.report_channel = Mock(spec=discord.TextChannel)
        self.report_channel.guild = Mock(spec=discord.Guild)

    def _create_context(self):
        return MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

    def _create_mock_handler(self, name: str, priority: int = 50, should_handle: bool = True):
        handler = Mock()
        handler.name = name
        handler.priority = priority
        handler.should_handle = Mock(return_value=should_handle)
        handler.handle = AsyncMock()
        return handler

    def test_register_adds_handler(self):
        """register() adds handler to internal list."""
        handler = self._create_mock_handler("TestHandler")

        self.emitter.register(handler)

        self.assertIn(handler, self.emitter._handlers)

    def test_register_marks_unsorted(self):
        """register() marks handlers as unsorted."""
        self.emitter._sorted = True
        handler = self._create_mock_handler("TestHandler")

        self.emitter.register(handler)

        self.assertFalse(self.emitter._sorted)

    def test_suppress_next_for_adds_id_to_suppressed(self):
        """suppress_next_for() adds discord ID to suppressed set."""
        discord_id = 12345

        self.emitter.suppress_next_for(discord_id)

        self.assertIn(discord_id, self.emitter._suppressed_ids)

    def test_is_suppressed_returns_true_and_removes_id(self):
        """_is_suppressed() returns True and removes ID when suppressed."""
        discord_id = 12345
        self.emitter._suppressed_ids.add(discord_id)

        result = self.emitter._is_suppressed(discord_id)

        self.assertTrue(result)
        self.assertNotIn(discord_id, self.emitter._suppressed_ids)

    def test_is_suppressed_returns_false_when_not_suppressed(self):
        """_is_suppressed() returns False when ID not suppressed."""
        discord_id = 12345

        result = self.emitter._is_suppressed(discord_id)

        self.assertFalse(result)

    def test_is_suppressed_one_shot(self):
        """_is_suppressed() is one-shot - second call returns False."""
        discord_id = 12345
        self.emitter._suppressed_ids.add(discord_id)

        first_result = self.emitter._is_suppressed(discord_id)
        second_result = self.emitter._is_suppressed(discord_id)

        self.assertTrue(first_result)
        self.assertFalse(second_result)

    def test_ensure_sorted_sorts_by_priority(self):
        """_ensure_sorted() sorts handlers by priority ascending."""
        handler1 = self._create_mock_handler("Handler1", priority=50)
        handler2 = self._create_mock_handler("Handler2", priority=10)
        handler3 = self._create_mock_handler("Handler3", priority=30)

        self.emitter.register(handler1)
        self.emitter.register(handler2)
        self.emitter.register(handler3)

        self.emitter._ensure_sorted()

        self.assertEqual(self.emitter._handlers[0], handler2)  # priority 10
        self.assertEqual(self.emitter._handlers[1], handler3)  # priority 30
        self.assertEqual(self.emitter._handlers[2], handler1)  # priority 50

    def test_ensure_sorted_marks_sorted(self):
        """_ensure_sorted() marks handlers as sorted."""
        self.emitter._sorted = False

        self.emitter._ensure_sorted()

        self.assertTrue(self.emitter._sorted)

    def test_ensure_sorted_skips_when_already_sorted(self):
        """_ensure_sorted() does nothing when already sorted."""
        handler1 = self._create_mock_handler("Handler1", priority=50)
        self.emitter.register(handler1)
        self.emitter._sorted = True

        original_handlers = self.emitter._handlers.copy()
        self.emitter._ensure_sorted()

        self.assertEqual(self.emitter._handlers, original_handlers)

    async def test_emit_returns_empty_list_when_suppressed(self):
        """emit() returns empty list when discord ID is suppressed."""
        context = self._create_context()
        self.emitter.suppress_next_for(context.discord_id)
        handler = self._create_mock_handler("TestHandler")
        self.emitter.register(handler)

        results = await self.emitter.emit(context)

        self.assertEqual(results, [])
        handler.should_handle.assert_not_called()
        handler.handle.assert_not_called()

    async def test_emit_calls_should_handle_for_each_handler(self):
        """emit() checks should_handle() for each registered handler."""
        context = self._create_context()
        handler1 = self._create_mock_handler("Handler1", should_handle=True)
        handler2 = self._create_mock_handler("Handler2", should_handle=False)
        self.emitter.register(handler1)
        self.emitter.register(handler2)

        await self.emitter.emit(context)

        handler1.should_handle.assert_called_once_with(context)
        handler2.should_handle.assert_called_once_with(context)

    async def test_emit_only_executes_matching_handlers(self):
        """emit() only calls handle() on handlers where should_handle returns True."""
        context = self._create_context()
        handler1 = self._create_mock_handler("Handler1", should_handle=True)
        handler2 = self._create_mock_handler("Handler2", should_handle=False)
        self.emitter.register(handler1)
        self.emitter.register(handler2)

        await self.emitter.emit(context)

        handler1.handle.assert_called_once_with(context)
        handler2.handle.assert_not_called()

    async def test_emit_executes_in_priority_order(self):
        """emit() executes handlers in priority order (lowest first)."""
        context = self._create_context()
        execution_order = []

        handler1 = self._create_mock_handler("Handler1", priority=50)
        handler1.handle = AsyncMock(side_effect=lambda c: execution_order.append("Handler1"))

        handler2 = self._create_mock_handler("Handler2", priority=10)
        handler2.handle = AsyncMock(side_effect=lambda c: execution_order.append("Handler2"))

        handler3 = self._create_mock_handler("Handler3", priority=30)
        handler3.handle = AsyncMock(side_effect=lambda c: execution_order.append("Handler3"))

        self.emitter.register(handler1)
        self.emitter.register(handler2)
        self.emitter.register(handler3)

        await self.emitter.emit(context)

        self.assertEqual(execution_order, ["Handler2", "Handler3", "Handler1"])

    async def test_emit_continues_after_handler_exception(self):
        """emit() continues processing remaining handlers after one fails."""
        context = self._create_context()

        handler1 = self._create_mock_handler("Handler1", priority=10)
        handler1.handle = AsyncMock(side_effect=ValueError("Test error"))

        handler2 = self._create_mock_handler("Handler2", priority=20)

        self.emitter.register(handler1)
        self.emitter.register(handler2)

        results = await self.emitter.emit(context)

        handler2.handle.assert_called_once_with(context)
        self.assertEqual(len(results), 2)

    async def test_emit_returns_handler_results(self):
        """emit() returns HandlerResult for each executed handler."""
        context = self._create_context()
        handler = self._create_mock_handler("TestHandler")
        self.emitter.register(handler)

        results = await self.emitter.emit(context)

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsInstance(result, HandlerResult)
        self.assertEqual(result.handler_name, "TestHandler")
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.duration_ms, 0)

    async def test_emit_returns_failure_result_on_exception(self):
        """emit() returns HandlerResult with error on handler exception."""
        context = self._create_context()
        error = ValueError("Test error")
        handler = self._create_mock_handler("TestHandler")
        handler.handle = AsyncMock(side_effect=error)
        self.emitter.register(handler)

        results = await self.emitter.emit(context)

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertFalse(result.success)
        self.assertEqual(result.error, error)

    async def test_emit_measures_timing(self):
        """emit() measures handler execution time in milliseconds."""
        context = self._create_context()

        async def slow_handle(c):
            import asyncio
            await asyncio.sleep(0.01)  # 10ms

        handler = self._create_mock_handler("TestHandler")
        handler.handle = slow_handle
        self.emitter.register(handler)

        results = await self.emitter.emit(context)

        self.assertGreaterEqual(results[0].duration_ms, 10)

    async def test_emit_skips_handlers_that_dont_match(self):
        """emit() returns results only for handlers that matched."""
        context = self._create_context()
        handler1 = self._create_mock_handler("Handler1", should_handle=True)
        handler2 = self._create_mock_handler("Handler2", should_handle=False)
        handler3 = self._create_mock_handler("Handler3", should_handle=True)
        self.emitter.register(handler1)
        self.emitter.register(handler2)
        self.emitter.register(handler3)

        results = await self.emitter.emit(context)

        self.assertEqual(len(results), 2)
        handler_names = [r.handler_name for r in results]
        self.assertIn("Handler1", handler_names)
        self.assertNotIn("Handler2", handler_names)
        self.assertIn("Handler3", handler_names)

    async def test_emit_empty_when_no_handlers(self):
        """emit() returns empty list when no handlers registered."""
        context = self._create_context()

        results = await self.emitter.emit(context)

        self.assertEqual(results, [])


class TestMemberUpdateEmitterSingleton(unittest.TestCase):
    def test_singleton_instance_exists(self):
        """member_update_emitter global instance exists."""
        from ironforgedbot.events.member_update_emitter import member_update_emitter

        self.assertIsInstance(member_update_emitter, MemberUpdateEmitter)
