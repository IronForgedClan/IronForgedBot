import unittest
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.services.member_service import MemberService
from tests.helpers import create_test_member


class ConcreteHandler(BaseMemberUpdateHandler):
    """Concrete implementation for testing BaseMemberUpdateHandler."""

    def __init__(self, execute_result: Optional[str] = None, execute_error: Exception = None):
        self._execute_result = execute_result
        self._execute_error = execute_error

    @property
    def name(self) -> str:
        return "ConcreteHandler"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return True

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        if self._execute_error:
            raise self._execute_error
        return self._execute_result


class TestBaseMemberUpdateHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.before = create_test_member("TestUser", ["Member"], "TestNick")
        self.after = create_test_member("TestUser", ["Member"], "TestNick")
        self.after.id = self.before.id
        self.report_channel = AsyncMock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()
        self.report_channel.guild = Mock(spec=discord.Guild)

        self.mock_session = AsyncMock(spec=AsyncSession)
        self.mock_service = Mock(spec=MemberService)

    def _create_context(self):
        return MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

    def test_default_priority(self):
        """Default priority is 50."""
        handler = ConcreteHandler()
        self.assertEqual(handler.priority, 50)

    async def test_on_error_default_returns_warning_message(self):
        """Default _on_error() returns warning message with handler name and error."""
        handler = ConcreteHandler()
        context = self._create_context()
        error = ValueError("Test error")

        result = await handler._on_error(context, error)

        self.assertIn("ConcreteHandler", result)
        self.assertIn("Test error", result)
        self.assertIn(":warning:", result)

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_handle_creates_db_session_and_service(self, mock_db):
        """handle() creates database session and MemberService."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        handler = ConcreteHandler()
        context = self._create_context()

        with patch.object(handler, "_execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = None
            await handler.handle(context)

            mock_execute.assert_called_once()
            call_args = mock_execute.call_args
            self.assertEqual(call_args[0][0], context)
            self.assertEqual(call_args[0][1], mock_session)
            self.assertIsInstance(call_args[0][2], MemberService)

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_handle_sends_message_when_execute_returns_string(self, mock_db):
        """handle() sends message to report channel when _execute() returns string."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        handler = ConcreteHandler(execute_result="Test message")
        context = self._create_context()

        await handler.handle(context)

        self.report_channel.send.assert_called_once_with("Test message")

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_handle_no_message_when_execute_returns_none(self, mock_db):
        """handle() does not send message when _execute() returns None."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        handler = ConcreteHandler(execute_result=None)
        context = self._create_context()

        await handler.handle(context)

        self.report_channel.send.assert_not_called()

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_handle_calls_on_error_on_exception(self, mock_db):
        """handle() calls _on_error() when _execute() raises exception."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        error = ValueError("Test error")
        handler = ConcreteHandler(execute_error=error)
        context = self._create_context()

        with self.assertRaises(ValueError):
            await handler.handle(context)

        # Verify error message was sent
        self.report_channel.send.assert_called_once()
        call_args = self.report_channel.send.call_args[0][0]
        self.assertIn("ConcreteHandler", call_args)
        self.assertIn("error", call_args.lower())

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_handle_reraises_exception_after_error_handling(self, mock_db):
        """handle() re-raises exception after calling _on_error()."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        error = ValueError("Test error")
        handler = ConcreteHandler(execute_error=error)
        context = self._create_context()

        with self.assertRaises(ValueError) as cm:
            await handler.handle(context)

        self.assertEqual(cm.exception, error)

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_handle_includes_duration_in_error_message(self, mock_db):
        """handle() includes execution duration in error message."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        error = ValueError("Test error")
        handler = ConcreteHandler(execute_error=error)
        context = self._create_context()

        with self.assertRaises(ValueError):
            await handler.handle(context)

        call_args = self.report_channel.send.call_args[0][0]
        self.assertIn("ms", call_args)


class TestBaseMemberUpdateHandlerCustomOnError(unittest.IsolatedAsyncioTestCase):
    """Test custom _on_error() implementations."""

    def setUp(self):
        self.before = create_test_member("TestUser", ["Member"], "TestNick")
        self.after = create_test_member("TestUser", ["Member"], "TestNick")
        self.after.id = self.before.id
        self.report_channel = AsyncMock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()
        self.report_channel.guild = Mock(spec=discord.Guild)

    def _create_context(self):
        return MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_custom_on_error_message_is_used(self, mock_db):
        """Custom _on_error() message is sent when provided."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        class CustomErrorHandler(BaseMemberUpdateHandler):
            @property
            def name(self) -> str:
                return "CustomErrorHandler"

            def should_handle(self, context: MemberUpdateContext) -> bool:
                return True

            async def _execute(
                self,
                context: MemberUpdateContext,
                session: AsyncSession,
                service: MemberService,
            ) -> Optional[str]:
                raise ValueError("Test error")

            async def _on_error(
                self,
                context: MemberUpdateContext,
                error: Exception,
            ) -> Optional[str]:
                return "Custom error message"

        handler = CustomErrorHandler()
        context = self._create_context()

        with self.assertRaises(ValueError):
            await handler.handle(context)

        call_args = self.report_channel.send.call_args[0][0]
        self.assertIn("Custom error message", call_args)

    @patch("ironforgedbot.events.handlers.base.db")
    async def test_on_error_returning_none_skips_message(self, mock_db):
        """When _on_error() returns None, no error message is sent."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_context_manager

        class SilentErrorHandler(BaseMemberUpdateHandler):
            @property
            def name(self) -> str:
                return "SilentErrorHandler"

            def should_handle(self, context: MemberUpdateContext) -> bool:
                return True

            async def _execute(
                self,
                context: MemberUpdateContext,
                session: AsyncSession,
                service: MemberService,
            ) -> Optional[str]:
                raise ValueError("Test error")

            async def _on_error(
                self,
                context: MemberUpdateContext,
                error: Exception,
            ) -> Optional[str]:
                return None  # Silent error

        handler = SilentErrorHandler()
        context = self._create_context()

        with self.assertRaises(ValueError):
            await handler.handle(context)

        self.report_channel.send.assert_not_called()
