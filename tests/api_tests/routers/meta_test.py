import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestMetaEndpoints(unittest.TestCase):
    def setUp(self):
        from api.audit import ApiAuditMiddleware
        from api.routers.meta import router
        from api.deps import get_db_session

        self.app = FastAPI()
        self.app.add_middleware(ApiAuditMiddleware)
        self.app.include_router(router)
        self.app.dependency_overrides[get_db_session] = self._override_db
        with patch("api.audit.db"):
            self.client = TestClient(self.app)

    async def _override_db(self):
        mock_session = AsyncMock(spec=AsyncSession)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_execute_result.scalar.return_value = None
        mock_session.execute.return_value = mock_execute_result
        yield mock_session

    def test_health_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["status"], "ok")
        self.assertEqual(body["data"]["db"], "ok")
        self.assertIn("version", body["data"])
        self.assertIn("environment", body["data"])

    def test_health_degraded_when_db_fails(self):
        from api.deps import get_db_session

        async def failing_db():
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.execute.side_effect = RuntimeError("db down")
            yield mock_session

        self.app.dependency_overrides[get_db_session] = failing_db
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["data"]["status"], "degraded")
        self.assertEqual(body["data"]["db"], "error")
