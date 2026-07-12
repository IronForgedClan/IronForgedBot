import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from tests.helpers import create_mock_db_session


class TestCheck(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from api import rate_limit

        rate_limit._buckets.clear()

    async def test_unlimited_short_circuits(self):
        from api.rate_limit import _check

        for _ in range(100):
            _check("any", 0)

    async def test_first_request_succeeds(self):
        from api.rate_limit import _check

        _check("k1", 5)

    async def test_blocks_at_limit_plus_one(self):
        from api.rate_limit import _check

        _check("k1", 2)
        _check("k1", 2)
        with self.assertRaises(HTTPException) as ctx:
            _check("k1", 2)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)
        retry = int(ctx.exception.headers["Retry-After"])
        self.assertGreaterEqual(retry, 1)
        self.assertLessEqual(retry, 60)

    async def test_separate_keys_have_separate_buckets(self):
        from api.rate_limit import _check

        _check("a", 2)
        _check("a", 2)
        _check("b", 2)
        _check("b", 2)
        with self.assertRaises(HTTPException):
            _check("a", 2)
        with self.assertRaises(HTTPException):
            _check("b", 2)

    async def test_window_resets_after_minute(self):
        from api import rate_limit
        from api.rate_limit import _check

        _check("k", 1)
        for k in list(rate_limit._buckets):
            rate_limit._buckets[k] = (0, 99)
        _check("k", 1)

    async def test_sweep_removes_stale_buckets(self):
        from api import rate_limit
        from api.rate_limit import _check, current_window

        rate_limit._buckets["stale"] = (0, 1)
        rate_limit._buckets["fresh"] = (current_window(), 1)
        _check("k", 10)
        self.assertNotIn("stale", rate_limit._buckets)
        self.assertIn("fresh", rate_limit._buckets)


class TestRateLimitFactory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from api import rate_limit

        rate_limit._buckets.clear()

    def _request(self, consumer=None):
        request = MagicMock()
        request.state.consumer = consumer
        request.url.path = "/x"
        request.method = "GET"
        request.headers = {}
        request.client = None
        return request

    def test_returns_async_callable(self):
        from api.rate_limit import rate_limit

        dep = rate_limit()
        self.assertTrue(callable(dep))
        self.assertTrue(asyncio.iscoroutinefunction(dep))

    async def test_sets_required_perm_on_request(self):
        from api.perm import requires_perm

        dep = requires_perm("x:read")
        request = self._request()
        consumer = MagicMock()
        consumer.perms = ["x:read"]
        await dep(request, consumer=consumer)
        self.assertEqual(request.state.required_perm, "x:read")

    async def test_keys_by_consumer_when_authed(self):
        from api import rate_limit
        from api.rate_limit import rate_limit

        dep = rate_limit(per_minute=1)
        consumer = {"id": 42, "name": "a", "perms": []}
        await dep(self._request(consumer=consumer), _consumer=MagicMock())
        with self.assertRaises(HTTPException):
            await dep(self._request(consumer=consumer), _consumer=MagicMock())

    async def test_keys_by_ip_when_unauth(self):
        from api.rate_limit import rate_limit

        dep = rate_limit(per_minute=1)
        with patch("api.rate_limit.get_client_ip", return_value="1.1.1.1"):
            await dep(self._request(), _consumer=MagicMock())
        with patch("api.rate_limit.get_client_ip", return_value="2.2.2.2"):
            await dep(self._request(), _consumer=MagicMock())
        with patch("api.rate_limit.get_client_ip", return_value="1.1.1.1"):
            with self.assertRaises(HTTPException):
                await dep(self._request(), _consumer=MagicMock())

    async def test_unlimited_allows_many(self):
        from api.rate_limit import rate_limit

        dep = rate_limit(per_minute=0)
        consumer = {"id": 1, "name": "a", "perms": []}
        for _ in range(50):
            await dep(self._request(consumer=consumer), _consumer=MagicMock())

    def test_default_reads_from_config(self):
        from api.rate_limit import rate_limit

        with patch("api.rate_limit.API_CONFIG") as mock_cfg:
            mock_cfg.API_RATE_LIMIT = 99
            dep = rate_limit()
            self.assertIsNotNone(dep)

    def test_no_required_perm_param(self):
        from api.rate_limit import rate_limit

        with self.assertRaises(TypeError):
            rate_limit(required_perm="x")


class TestPublicRateLimitFactory(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from api import rate_limit

        rate_limit._buckets.clear()

    def _request(self):
        request = MagicMock()
        request.url.path = "/health"
        request.method = "GET"
        request.headers = {}
        request.client = None
        return request

    def test_no_auth_subdep(self):
        from api.rate_limit import public_rate_limit

        dep = public_rate_limit()
        sig = dep.__wrapped__ if hasattr(dep, "__wrapped__") else dep
        import inspect

        params = list(inspect.signature(sig).parameters)
        self.assertNotIn("_consumer", params)
        self.assertNotIn("consumer", params)

    async def test_blocks_after_limit(self):
        from api.rate_limit import public_rate_limit

        dep = public_rate_limit(per_minute=2)
        with patch("api.rate_limit.get_client_ip", return_value="9.9.9.9"):
            await dep(self._request())
            await dep(self._request())
            with self.assertRaises(HTTPException):
                await dep(self._request())


class TestRateLimitAuditIntegration(unittest.TestCase):
    def _build_protected_app(self, per_minute=2, required_perm="members:read"):
        from api.audit import ApiAuditMiddleware
        from api.errors import install_error_handlers
        from api.perm import requires_perm
        from api.rate_limit import rate_limit
        from fastapi import Depends, Request

        app = FastAPI()
        install_error_handlers(app)
        mock_db_patcher = patch("api.audit.db")
        mock_db = mock_db_patcher.start()
        mock_session = create_mock_db_session()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_ctx
        self.addCleanup(mock_db_patcher.stop)
        app.add_middleware(ApiAuditMiddleware)
        rl = rate_limit(per_minute=per_minute)
        perm = requires_perm(required_perm)

        async def fake_auth_dep(request: Request):
            from api.models import ApiConsumer

            request.state.consumer = {
                "id": 42,
                "name": "test-consumer",
                "perms": ["members:read"],
            }
            return ApiConsumer(
                id=42,
                name="test-consumer",
                token_hash="x",
                perms=["members:read"],
                enabled=True,
            )

        from api.deps import get_current_consumer

        @app.get(
            "/protected",
            dependencies=[Depends(perm), Depends(rl)],
        )
        async def protected():
            return {"ok": True}

        app.dependency_overrides[get_current_consumer] = fake_auth_dep
        return app, mock_session

    def _build_public_app(self, per_minute=2):
        from api.audit import ApiAuditMiddleware
        from api.errors import install_error_handlers
        from api.rate_limit import public_rate_limit
        from fastapi import Depends

        app = FastAPI()
        install_error_handlers(app)
        mock_db_patcher = patch("api.audit.db")
        mock_db = mock_db_patcher.start()
        mock_session = create_mock_db_session()
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_ctx
        self.addCleanup(mock_db_patcher.stop)
        app.add_middleware(ApiAuditMiddleware)
        rl = public_rate_limit(per_minute=per_minute)

        @app.get("/public", dependencies=[Depends(rl)])
        async def public():
            return {"ok": True}

        return app, mock_session

    def _audit_rows(self, mock_session):
        from api.audit import ApiAudit

        added = [c.args[0] for c in mock_session.add.call_args_list]
        return [a for a in added if isinstance(a, ApiAudit)]

    def test_protected_429_audit_row_has_complete_consumer_info(self):
        from api import rate_limit

        rate_limit._buckets.clear()
        app, mock_session = self._build_protected_app(per_minute=2)
        client = TestClient(app)
        with patch("api.rate_limit.get_client_ip", return_value="5.5.5.5"):
            client.get("/protected", headers={"x-forwarded-for": "5.5.5.5"})
            client.get("/protected", headers={"x-forwarded-for": "5.5.5.5"})
            r3 = client.get("/protected", headers={"x-forwarded-for": "5.5.5.5"})

        self.assertEqual(r3.status_code, 429)
        rows = self._audit_rows(mock_session)
        rate_limited = [r for r in rows if r.status_code == 429]
        self.assertEqual(len(rate_limited), 1)
        row = rate_limited[0]
        self.assertEqual(row.consumer_id, 42)
        self.assertEqual(row.consumer_name, "test-consumer")
        self.assertEqual(row.consumer_perms, ["members:read"])
        self.assertEqual(row.required_perm, "members:read")

    def test_public_429_audit_row_has_no_consumer(self):
        from api import rate_limit

        rate_limit._buckets.clear()
        app, mock_session = self._build_public_app(per_minute=1)
        client = TestClient(app)
        with patch("api.rate_limit.get_client_ip", return_value="7.7.7.7"):
            r1 = client.get("/public", headers={"x-forwarded-for": "7.7.7.7"})
            r2 = client.get("/public", headers={"x-forwarded-for": "7.7.7.7"})

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 429)
        rows = self._audit_rows(mock_session)
        rate_limited = [r for r in rows if r.status_code == 429]
        self.assertEqual(len(rate_limited), 1)
        row = rate_limited[0]
        self.assertIsNone(row.consumer_id)
        self.assertIsNone(row.consumer_name)
        self.assertIsNone(row.consumer_perms)
        self.assertIsNone(row.required_perm)


if __name__ == "__main__":
    unittest.main()
