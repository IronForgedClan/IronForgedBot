import logging
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from starlette.exceptions import HTTPException as StarletteHTTPException


def _build_db_with_mock_session(
    raise_inside: BaseException,
) -> tuple[MagicMock, "Database"]:
    from ironforgedbot.database.database import Database

    db = Database(url="sqlite+aiosqlite:///:memory:")
    db._initialized = True

    mock_session = MagicMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    @asynccontextmanager
    async def fake_session_factory():
        try:
            yield mock_session
        finally:
            pass

    db._SessionFactory = fake_session_factory

    return mock_session, db


class TestGetSessionLogging(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import logging

        self._previous_disable = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, self._previous_disable)

    async def test_http_exception_does_not_log_at_error_level(self):
        from ironforgedbot.database.database import Database

        mock_session, db = _build_db_with_mock_session(StarletteHTTPException(403))

        with self.assertLogs("ironforgedbot.database.database", level="DEBUG") as cm:
            with self.assertRaises(StarletteHTTPException):
                async with db.get_session():
                    raise StarletteHTTPException(
                        status_code=403, detail="Missing required permission"
                    )

        log_levels = [record.levelname for record in cm.records]
        self.assertNotIn("ERROR", log_levels)
        self.assertIn("DEBUG", log_levels)
        mock_session.rollback.assert_awaited_once()

    async def test_unexpected_exception_logs_at_error_level(self):
        from ironforgedbot.database.database import Database

        mock_session, db = _build_db_with_mock_session(RuntimeError("boom"))

        with self.assertLogs("ironforgedbot.database.database", level="ERROR") as cm:
            with self.assertRaises(RuntimeError):
                async with db.get_session():
                    raise RuntimeError("db connection lost")

        error_records = [r for r in cm.records if r.levelname == "ERROR"]
        self.assertEqual(len(error_records), 1)
        self.assertIn("db connection lost", error_records[0].getMessage())
        self.assertIsNotNone(error_records[0].exc_info)
        mock_session.rollback.assert_awaited_once()

    async def test_fastapi_http_exception_is_treated_as_expected(self):
        from fastapi import HTTPException as FastAPIHTTPException

        from ironforgedbot.database.database import Database

        mock_session, db = _build_db_with_mock_session(FastAPIHTTPException(404))

        with self.assertLogs("ironforgedbot.database.database", level="DEBUG") as cm:
            with self.assertRaises(FastAPIHTTPException):
                async with db.get_session():
                    raise FastAPIHTTPException(status_code=404, detail="not found")

        log_levels = [record.levelname for record in cm.records]
        self.assertNotIn("ERROR", log_levels)
        mock_session.rollback.assert_awaited_once()
