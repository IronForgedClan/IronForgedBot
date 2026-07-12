import unittest

from api.models import ApiAudit, ApiConsumer


class TestApiConsumer(unittest.TestCase):
    def test_tablename(self):
        self.assertEqual(ApiConsumer.__tablename__, "api_consumers")

    def test_columns(self):
        cols = {c.name for c in ApiConsumer.__table__.columns}
        expected = {
            "id",
            "name",
            "token_hash",
            "perms",
            "enabled",
            "created_at",
            "last_used_at",
            "description",
        }
        self.assertEqual(cols, expected)

    def test_perms_is_json(self):
        perms_col = ApiConsumer.__table__.columns["perms"]
        self.assertEqual(perms_col.type.__class__.__name__, "JSON")


class TestApiAudit(unittest.TestCase):
    def test_tablename(self):
        self.assertEqual(ApiAudit.__tablename__, "api_audit")

    def test_columns(self):
        cols = {c.name for c in ApiAudit.__table__.columns}
        expected = {
            "id",
            "timestamp",
            "request_id",
            "consumer_id",
            "consumer_name",
            "consumer_perms",
            "required_perm",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
            "user_agent",
            "error",
        }
        self.assertEqual(cols, expected)

    def test_path_max_length(self):
        path_col = ApiAudit.__table__.columns["path"]
        self.assertEqual(path_col.type.length, 512)

    def test_request_id_max_length(self):
        request_id_col = ApiAudit.__table__.columns["request_id"]
        self.assertEqual(request_id_col.type.length, 36)
        self.assertFalse(request_id_col.nullable)
