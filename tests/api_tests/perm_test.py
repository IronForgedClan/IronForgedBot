import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiConsumer
from tests.helpers import create_mock_db_session


class TestRequiresPermDep(unittest.IsolatedAsyncioTestCase):
    async def _run_dep(self, perm: str, consumer_perms: list[str] | None):
        from api.perm import requires_perm

        dep = requires_perm(perm)
        request = MagicMock()
        request.state.consumer = {
            "id": 1,
            "name": "test",
            "perms": consumer_perms,
        }
        consumer = ApiConsumer(
            id=1,
            name="test",
            token_hash="x",
            perms=consumer_perms,
            enabled=True,
        )
        await dep(request, consumer=consumer)
        return request

    async def test_sets_required_perm_on_request(self):
        request = await self._run_dep("x:read", ["x:read"])
        self.assertEqual(request.state.required_perm, "x:read")

    async def test_consumer_with_perm_passes(self):
        await self._run_dep("members:read", ["members:read", "scores:read"])

    async def test_consumer_without_perm_raises_403(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._run_dep("members:read", ["scores:read"])
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("members:read", str(ctx.exception.detail))

    async def test_empty_perms_denied(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._run_dep("meta:read", [])
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_none_perms_treated_as_empty(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            await self._run_dep("meta:read", None)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_perms_exact_match_required(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            await self._run_dep("ingots:read", ["ingots:read:transactions"])

    async def test_perms_no_inheritance(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            await self._run_dep("scores:read", ["scores:read:history"])


class TestRequiresPermAuditIntegration(unittest.TestCase):
    def _build_app(self, required_perm: str = "members:read", rate_per_minute: int = 2):
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
        rl = rate_limit(per_minute=rate_per_minute)
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

    def _audit_rows(self, mock_session):
        from api.audit import ApiAudit

        added = [c.args[0] for c in mock_session.add.call_args_list]
        return [a for a in added if isinstance(a, ApiAudit)]

    def test_403_audit_row_has_required_perm(self):
        from api.rate_limit import _buckets

        _buckets.clear()
        app, mock_session = self._build_app(
            required_perm="admin:do", rate_per_minute=100
        )
        client = TestClient(app)
        client.get("/protected", headers={"x-forwarded-for": "1.1.1.1"})

        rows = self._audit_rows(mock_session)
        forbidden = [r for r in rows if r.status_code == 403]
        self.assertEqual(len(forbidden), 1)
        self.assertEqual(forbidden[0].required_perm, "admin:do")

    def test_429_audit_row_has_required_perm_when_perm_declared_first(self):
        from api.rate_limit import _buckets

        _buckets.clear()
        app, mock_session = self._build_app(
            required_perm="members:read", rate_per_minute=1
        )
        client = TestClient(app)
        client.get("/protected", headers={"x-forwarded-for": "2.2.2.2"})
        client.get("/protected", headers={"x-forwarded-for": "2.2.2.2"})

        rows = self._audit_rows(mock_session)
        rate_limited = [r for r in rows if r.status_code == 429]
        self.assertEqual(len(rate_limited), 1)
        self.assertEqual(rate_limited[0].required_perm, "members:read")


if __name__ == "__main__":
    unittest.main()
