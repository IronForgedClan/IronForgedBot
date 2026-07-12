import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from tests.helpers import create_mock_db_session


class TestAuditMiddleware(unittest.TestCase):
    def setUp(self):
        from api.audit import ApiAuditMiddleware

        self.app = FastAPI()
        self.app.add_middleware(ApiAuditMiddleware)

        @self.app.get("/test")
        async def handler():
            return {"ok": True}

        @self.app.get("/fail")
        async def fail():
            raise ValueError("boom")

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_writes_audit_row_on_success(self):
        from api.audit import ApiAudit

        with patch("api.audit.db") as mock_db:
            mock_session = create_mock_db_session()
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            response = self.client.get("/test")

            self.assertEqual(response.status_code, 200)
            added = [call.args[0] for call in mock_session.add.call_args_list]
            audit_rows = [a for a in added if isinstance(a, ApiAudit)]
            self.assertEqual(len(audit_rows), 1)
            row = audit_rows[0]
            self.assertEqual(row.method, "GET")
            self.assertEqual(row.path, "/test")
            self.assertEqual(row.status_code, 200)
            self.assertGreaterEqual(row.duration_ms, 0)
            self.assertIsNone(row.error)

    def test_writes_audit_row_on_exception(self):
        from api.audit import ApiAudit

        with patch("api.audit.db") as mock_db:
            mock_session = create_mock_db_session()
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            response = self.client.get("/fail")

            self.assertEqual(response.status_code, 500)
            added = [call.args[0] for call in mock_session.add.call_args_list]
            audit_rows = [a for a in added if isinstance(a, ApiAudit)]
            self.assertEqual(len(audit_rows), 1)
            row = audit_rows[0]
            self.assertEqual(row.status_code, 500)
            self.assertIsNotNone(row.error)
            self.assertIn("boom", row.error)

    def test_audit_row_strips_query_string_from_path(self):
        from api.audit import ApiAudit

        with patch("api.audit.db") as mock_db:
            mock_session = create_mock_db_session()
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            self.client.get("/test?secret=value&token=abc")

            added = [call.args[0] for call in mock_session.add.call_args_list]
            audit_rows = [a for a in added if isinstance(a, ApiAudit)]
            self.assertEqual(len(audit_rows), 1)
            self.assertEqual(audit_rows[0].path, "/test")

    def test_audit_row_truncates_long_path(self):
        from api.audit import ApiAudit

        app = FastAPI()
        from api.audit import ApiAuditMiddleware

        app.add_middleware(ApiAuditMiddleware)

        @app.get("/long")
        async def long_path(request: Request):
            return JSONResponse({"ok": True})

        client = TestClient(app, raise_server_exceptions=False)
        long_segment = "a" * 600

        with patch("api.audit.db") as mock_db:
            mock_session = create_mock_db_session()
            mock_ctx = MagicMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            client.get(f"/long?p={long_segment}")

            added = [call.args[0] for call in mock_session.add.call_args_list]
            audit_rows = [a for a in added if isinstance(a, ApiAudit)]
            self.assertEqual(len(audit_rows), 1)
            self.assertLessEqual(len(audit_rows[0].path), 512)


class TestAuditConsumerSnapshot(unittest.TestCase):
    def setUp(self):
        from fastapi import Depends, FastAPI, Request

        from api.audit import ApiAuditMiddleware
        from api.deps import get_current_consumer
        from api.errors import install_error_handlers

        self.app = FastAPI()
        self.app.add_middleware(ApiAuditMiddleware)
        install_error_handlers(self.app)

        self.snapshot = {
            "id": 42,
            "name": "tester",
            "perms": ["members:read"],
        }

        async def override_consumer(request: Request):
            request.state.consumer = self.snapshot
            return self.snapshot

        self.app.dependency_overrides[get_current_consumer] = override_consumer

        @self.app.get("/fail")
        async def fail(consumer=Depends(get_current_consumer)):
            raise HTTPException(
                status_code=404,
                detail="not found",
            )

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _patch_audit_db(self):
        mock_db = patch("api.audit.db").start()
        mock_session = create_mock_db_session()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_ctx
        self.addCleanup(patch.stopall)
        return mock_session

    def test_writes_audit_row_on_http_exception_with_consumer_snapshot(self):
        from api.audit import ApiAudit

        mock_session = self._patch_audit_db()

        response = self.client.get("/fail")

        self.assertEqual(response.status_code, 404)
        added = [call.args[0] for call in mock_session.add.call_args_list]
        audit_rows = [a for a in added if isinstance(a, ApiAudit)]
        self.assertEqual(len(audit_rows), 1)
        row = audit_rows[0]
        self.assertEqual(row.status_code, 404)
        self.assertEqual(row.consumer_id, 42)
        self.assertEqual(row.consumer_name, "tester")
        self.assertEqual(row.consumer_perms, ["members:read"])

    def test_writes_audit_row_on_http_exception_when_consumer_snapshot_missing(self):
        from fastapi import Depends, Request, status

        async def override_consumer(request: Request):
            return None

        from api.deps import get_current_consumer

        self.app.dependency_overrides[get_current_consumer] = override_consumer

        @self.app.get("/perm")
        async def perm(consumer=Depends(get_current_consumer)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing required permission: members:read",
            )

        from api.audit import ApiAudit

        mock_session = self._patch_audit_db()

        response = self.client.get("/perm")

        self.assertEqual(response.status_code, 403)
        added = [call.args[0] for call in mock_session.add.call_args_list]
        audit_rows = [a for a in added if isinstance(a, ApiAudit)]
        self.assertEqual(len(audit_rows), 1)
        row = audit_rows[0]
        self.assertEqual(row.status_code, 403)
        self.assertIsNone(row.consumer_id)
        self.assertIsNone(row.consumer_name)
        self.assertIsNone(row.consumer_perms)


class TestGetCurrentConsumerSnapshot(unittest.IsolatedAsyncioTestCase):
    async def test_creates_plain_dict_snapshot_on_request_state(self):
        from api.deps import get_current_consumer
        from api.models import ApiConsumer
        from fastapi import Request

        consumer = ApiConsumer(
            id=7,
            name="snapshotted",
            token_hash="x",
            perms=["a", "b"],
            enabled=True,
        )

        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer x"}
        request.state.consumer = None

        async def fake_verify_bearer(auth_header, session):
            return consumer

        session = MagicMock()

        with patch("api.deps.verify_bearer", fake_verify_bearer):
            result = await get_current_consumer(request, session)

        self.assertIs(result, consumer)
        self.assertIsInstance(request.state.consumer, dict)
        self.assertEqual(request.state.consumer["id"], 7)
        self.assertEqual(request.state.consumer["name"], "snapshotted")
        self.assertEqual(request.state.consumer["perms"], ["a", "b"])

    async def test_snapshot_handles_none_perms(self):
        from api.deps import get_current_consumer
        from api.models import ApiConsumer
        from fastapi import Request

        consumer = ApiConsumer(
            id=8,
            name="noperms",
            token_hash="x",
            perms=None,
            enabled=True,
        )

        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer x"}
        request.state.consumer = None

        async def fake_verify_bearer(auth_header, session):
            return consumer

        session = MagicMock()

        with patch("api.deps.verify_bearer", fake_verify_bearer):
            await get_current_consumer(request, session)

        self.assertEqual(request.state.consumer["perms"], [])


class TestRequestIdCorrelation(unittest.TestCase):
    def setUp(self):
        from api.audit import ApiAuditMiddleware
        from api.errors import install_error_handlers
        from api.schemas.common import ApiResponse, ResponseMeta

        self.app = FastAPI()
        self.app.add_middleware(ApiAuditMiddleware)
        install_error_handlers(self.app)

        @self.app.get("/ok")
        async def ok(request: Request):
            return ApiResponse(
                data={"ok": True},
                meta=ResponseMeta(request_id=request.state.request_id),
            )

        @self.app.get("/http-fail")
        async def http_fail():
            raise HTTPException(status_code=404, detail="not found")

        @self.app.get("/boom")
        async def boom():
            raise ValueError("kaboom")

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _patch_audit_db(self):
        mock_db = patch("api.audit.db").start()
        mock_session = create_mock_db_session()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_ctx
        self.addCleanup(patch.stopall)
        return mock_session

    def _audit_row(self, mock_session):
        from api.audit import ApiAudit

        added = [call.args[0] for call in mock_session.add.call_args_list]
        rows = [a for a in added if isinstance(a, ApiAudit)]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_success_response_meta_header_and_audit_row_share_request_id(self):
        mock_session = self._patch_audit_db()

        response = self.client.get("/ok")

        self.assertEqual(response.status_code, 200)
        self.assertIn("x-request-id", response.headers)
        body_id = response.json()["meta"]["request_id"]
        header_id = response.headers["x-request-id"]
        row = self._audit_row(mock_session)

        self.assertEqual(body_id, header_id)
        self.assertEqual(row.request_id, header_id)

    def test_http_error_response_meta_header_and_audit_row_share_request_id(self):
        mock_session = self._patch_audit_db()

        response = self.client.get("/http-fail")

        self.assertEqual(response.status_code, 404)
        self.assertIn("x-request-id", response.headers)
        body_id = response.json()["meta"]["request_id"]
        header_id = response.headers["x-request-id"]
        row = self._audit_row(mock_session)

        self.assertEqual(body_id, header_id)
        self.assertEqual(row.request_id, header_id)

    def test_unhandled_exception_audit_row_carries_request_id(self):
        mock_session = self._patch_audit_db()

        self.client.get("/boom")

        row = self._audit_row(mock_session)
        self.assertEqual(row.status_code, 500)
        self.assertEqual(len(row.request_id), 36)
        self.assertIn("-", row.request_id)

    def test_request_id_is_uuid_format(self):
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )

        self._patch_audit_db()

        response = self.client.get("/ok")
        request_id = response.json()["meta"]["request_id"]
        self.assertEqual(len(request_id), 36)
        self.assertRegex(request_id, uuid_pattern)

    def test_request_id_unique_per_request(self):
        self._patch_audit_db()

        first = self.client.get("/ok").headers["x-request-id"]
        second = self.client.get("/ok").headers["x-request-id"]

        self.assertNotEqual(first, second)
