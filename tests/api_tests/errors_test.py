import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ironforgedbot.services.member_service import MemberNotFoundException


def _build_app_with_handler() -> FastAPI:
    from api.audit import ApiAuditMiddleware
    from api.errors import install_error_handlers

    app = FastAPI()
    app.add_middleware(ApiAuditMiddleware)
    install_error_handlers(app)

    @app.get("/raise/missing")
    async def _raise_missing():
        raise MemberNotFoundException("No member with id=42")

    @app.get("/raise/default")
    async def _raise_default():
        raise MemberNotFoundException()

    return app


class TestMemberNotFoundHandler(unittest.TestCase):
    def setUp(self):
        with patch("api.audit.db"):
            self.app = _build_app_with_handler()
            self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_member_not_found_returns_404(self):
        response = self.client.get("/raise/missing")

        self.assertEqual(response.status_code, 404)

    def test_member_not_found_message_preserved(self):
        response = self.client.get("/raise/missing")

        body = response.json()
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["message"], "No member with id=42")

    def test_member_not_found_default_message(self):
        response = self.client.get("/raise/default")

        body = response.json()
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["message"], "The member can not be found")

    def test_member_not_found_includes_request_id(self):
        response = self.client.get("/raise/missing")

        body = response.json()
        self.assertIn("meta", body)
        self.assertIn("request_id", body["meta"])
        self.assertTrue(len(body["meta"]["request_id"]) > 0)
