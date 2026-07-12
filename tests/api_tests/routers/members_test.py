import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.models import Member
from ironforgedbot.services.member_service import (
    MemberListFilter,
    MemberListResult,
    MemberNotFoundException,
)

from tests.api_tests.helpers import build_test_app, build_test_client, make_consumer
from tests.helpers import create_mock_db_session


def _make_member(
    id: str | None = None,
    discord_id: int = 111,
    nickname: str = "tester",
    role: ROLE = ROLE.MEMBER,
    rank: RANK = RANK.IRON,
    is_booster: bool = False,
    is_prospect: bool = False,
    is_blacklisted: bool = False,
    is_banned: bool = False,
    active: bool = True,
) -> MagicMock:
    m = MagicMock(spec=Member)
    m.id = id if id is not None else str(uuid.uuid4())
    m.discord_id = discord_id
    m.nickname = nickname
    m.role = role
    m.rank = rank
    m.joined_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    m.is_booster = is_booster
    m.is_prospect = is_prospect
    m.is_blacklisted = is_blacklisted
    m.is_banned = is_banned
    m.active = active
    return m


class TestListMembers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.members import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["members:list"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    def test_list_returns_active_members_by_default(self):
        members = [_make_member(discord_id=1), _make_member(discord_id=2)]
        service_result = MemberListResult(members=members, total=2)
        with patch(
            "ironforgedbot.services.member_service.MemberService.list_members",
            new=AsyncMock(return_value=service_result),
        ):
            response = self.client.get("/members")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["total"], 2)
        self.assertEqual(len(body["data"]["members"]), 2)
        self.assertEqual(body["data"]["members"][0]["discord_id"], 1)

    def test_list_filters_by_role(self):
        service_result = MemberListResult(members=[], total=0)
        mock_service = AsyncMock(return_value=service_result)
        with patch(
            "ironforgedbot.services.member_service.MemberService.list_members",
            new=mock_service,
        ):
            response = self.client.get("/members?role=Member")

        self.assertEqual(response.status_code, 200)
        kwargs = mock_service.call_args.kwargs
        self.assertEqual(kwargs["role"], "Member")

    def test_list_passes_filter_booster_to_service(self):
        service_result = MemberListResult(members=[], total=0)
        mock_service = AsyncMock(return_value=service_result)
        with patch(
            "ironforgedbot.services.member_service.MemberService.list_members",
            new=mock_service,
        ):
            response = self.client.get("/members?filter=booster")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mock_service.call_args.kwargs["filter"], MemberListFilter.BOOSTER
        )

    def test_list_passes_filter_banned_to_service(self):
        service_result = MemberListResult(members=[], total=0)
        mock_service = AsyncMock(return_value=service_result)
        with patch(
            "ironforgedbot.services.member_service.MemberService.list_members",
            new=mock_service,
        ):
            response = self.client.get("/members?filter=banned")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mock_service.call_args.kwargs["filter"], MemberListFilter.BANNED
        )

    def test_list_passes_rank_to_service(self):
        service_result = MemberListResult(members=[], total=0)
        mock_service = AsyncMock(return_value=service_result)
        with patch(
            "ironforgedbot.services.member_service.MemberService.list_members",
            new=mock_service,
        ):
            response = self.client.get("/members?rank=Mithril")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_service.call_args.kwargs["rank"], "Mithril")

    def test_list_pagination(self):
        page_members = [_make_member(discord_id=i) for i in range(100, 150)]
        service_result = MemberListResult(members=page_members, total=250)
        with patch(
            "ironforgedbot.services.member_service.MemberService.list_members",
            new=AsyncMock(return_value=service_result),
        ):
            response = self.client.get("/members?limit=50&offset=100")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["total"], 250)
        self.assertEqual(body["data"]["limit"], 50)
        self.assertEqual(body["data"]["offset"], 100)

    def test_list_rejects_excessive_limit(self):
        response = self.client.get("/members?limit=10000")
        self.assertEqual(response.status_code, 422)

    def test_list_requires_auth(self):
        from api.routers.members import router
        from api.audit import ApiAuditMiddleware
        from api.errors import install_error_handlers
        from api.deps import get_current_consumer, get_db_session
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(ApiAuditMiddleware)
        install_error_handlers(app)
        app.include_router(router)

        mock_session = AsyncMock(spec=AsyncSession)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute_result

        async def db():
            yield mock_session

        app.dependency_overrides[get_db_session] = db

        with patch("api.audit.db") as mock_audit_db:
            audit_session = create_mock_db_session()
            audit_ctx = MagicMock()
            audit_ctx.__aenter__ = AsyncMock(return_value=audit_session)
            audit_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_audit_db.get_session.return_value = audit_ctx
            client = TestClient(app)
            response = client.get("/members")

        self.assertEqual(response.status_code, 401)


class TestGetMember(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.members import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["members:read"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    async def test_get_member_found(self):
        member = _make_member(
            id="11111111-2222-3333-4444-555555555555",
            discord_id=42,
            nickname="alice",
        )
        with patch(
            "ironforgedbot.services.member_service.MemberService.get_member_by_id_or_discord",
            new=AsyncMock(return_value=member),
        ):
            response = self.client.get("/members/42")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["id"], "11111111-2222-3333-4444-555555555555")
        self.assertEqual(body["data"]["discord_id"], 42)
        self.assertEqual(body["data"]["nickname"], "alice")
        self.assertNotIn("ingots", body["data"])
        self.assertNotIn("last_changed_date", body["data"])

    async def test_get_member_not_found(self):
        with patch(
            "ironforgedbot.services.member_service.MemberService.get_member_by_id_or_discord_or_raise",
            new=AsyncMock(
                side_effect=MemberNotFoundException("No member with id=999999")
            ),
        ):
            response = self.client.get("/members/999999")

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["message"], "No member with id=999999")

    async def test_get_member_by_internal_id_found(self):
        member = _make_member(
            id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            discord_id=99,
            nickname="bob",
        )
        with patch(
            "ironforgedbot.services.member_service.MemberService.get_member_by_id_or_discord",
            new=AsyncMock(return_value=member),
        ):
            response = self.client.get("/members/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["id"], "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        self.assertEqual(body["data"]["discord_id"], 99)
        self.assertEqual(body["data"]["nickname"], "bob")

    async def test_get_member_by_internal_id_not_found(self):
        with patch(
            "ironforgedbot.services.member_service.MemberService.get_member_by_id_or_discord_or_raise",
            new=AsyncMock(
                side_effect=MemberNotFoundException(
                    "No member with id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                )
            ),
        ):
            response = self.client.get("/members/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error"]["code"], "not_found")


class TestListMembersPermDenied(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.members import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["scores:read"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    def test_list_perm_denied_returns_403(self):
        response = self.client.get("/members")
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertIn("members:list", body["error"]["message"])

    def test_members_read_alone_does_not_grant_list(self):
        from api.routers.members import router

        consumer = make_consumer(perms=["members:read"])
        client = build_test_client(self.app, self.session, consumer)
        response = client.get("/members")
        self.assertEqual(response.status_code, 403)
        self.assertIn("members:list", response.json()["error"]["message"])


class TestGetMemberPermDenied(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.members import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["scores:read"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    def test_get_perm_denied_returns_403(self):
        response = self.client.get("/members/42")
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertIn("members:read", body["error"]["message"])

    def test_members_list_alone_does_not_grant_get(self):
        consumer = make_consumer(perms=["members:list"])
        client = build_test_client(self.app, self.session, consumer)
        response = client.get("/members/42")
        self.assertEqual(response.status_code, 403)
        self.assertIn("members:read", response.json()["error"]["message"])
