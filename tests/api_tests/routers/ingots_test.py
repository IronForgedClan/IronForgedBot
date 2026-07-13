import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedcore.common.ranks import RANK
from ironforgedcore.common.roles import ROLE
from ironforgedcore.models import Changelog, Member
from ironforgedcore.models.changelog import ChangeType
from ironforgedcore.services.member_service import MemberNotFoundException

from tests.api_tests.helpers import build_test_app, build_test_client, make_consumer


def _make_member(
    id: str | None = None,
    discord_id: int = 42,
    ingots: int = 100,
) -> MagicMock:
    m = MagicMock(spec=Member)
    m.id = id if id is not None else str(uuid.uuid4())
    m.discord_id = discord_id
    m.nickname = "alice"
    m.role = ROLE.MEMBER
    m.rank = RANK.IRON
    m.ingots = ingots
    m.joined_date = None
    m.is_booster = False
    m.is_prospect = False
    m.is_blacklisted = False
    m.is_banned = False
    m.active = True
    return m


def _make_log(
    id_: int = 1,
    change_type: ChangeType = ChangeType.ADD_INGOTS,
    admin_id: str | None = None,
    admin_member: MagicMock | None = None,
) -> MagicMock:
    log = MagicMock(spec=Changelog)
    log.id = id_
    log.change_type = change_type
    log.previous_value = "0"
    log.new_value = "100"
    log.comment = "test"
    log.admin_id = admin_id
    log.admin_member = admin_member
    log.timestamp = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return log


def _make_admin(
    id_: str = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
    discord_id: int = 7,
    nickname: str = "mod",
) -> MagicMock:
    m = MagicMock(spec=Member)
    m.id = id_
    m.discord_id = discord_id
    m.nickname = nickname
    return m


class TestGetMemberIngots(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.ingots import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["ingots:read"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    async def test_returns_balance(self):
        member = _make_member(discord_id=42, ingots=500)
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_id_or_discord",
            new=AsyncMock(return_value=member),
        ):
            response = self.client.get("/members/42/ingots")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("discord_id", body["data"])
        self.assertEqual(body["data"]["ingots"], 500)
        self.assertEqual(body["data"]["nickname"], "alice")

    async def test_member_not_found_404(self):
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_id_or_discord_or_raise",
            new=AsyncMock(
                side_effect=MemberNotFoundException("No member with id=999999")
            ),
        ):
            response = self.client.get("/members/999999/ingots")

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["message"], "No member with id=999999")

    async def test_get_member_ingots_by_internal_id(self):
        member = _make_member(
            id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            discord_id=99,
            ingots=750,
        )
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_id_or_discord",
            new=AsyncMock(return_value=member),
        ):
            response = self.client.get(
                "/members/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/ingots"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("discord_id", body["data"])
        self.assertEqual(body["data"]["ingots"], 750)

    def test_perm_denied_403(self):
        from api.routers.ingots import router

        consumer = make_consumer(perms=["scores:read"])
        client = build_test_client(self.app, self.session, consumer)
        response = client.get("/members/42/ingots")
        self.assertEqual(response.status_code, 403)


class TestGetMemberIngotTransactions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.ingots import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["ingots:read:transactions"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    async def test_returns_transactions(self):
        member = _make_member(discord_id=42)
        admin = _make_admin()
        logs = [
            _make_log(
                id_=1,
                change_type=ChangeType.ADD_INGOTS,
                admin_id=admin.id,
                admin_member=admin,
            ),
            _make_log(
                id_=2,
                change_type=ChangeType.REMOVE_INGOTS,
                admin_id=None,
                admin_member=None,
            ),
        ]
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_id_or_discord",
            new=AsyncMock(return_value=member),
        ):
            with patch(
                "ironforgedcore.services.changelog_service.ChangelogService.latest_ingot_transactions",
                new=AsyncMock(return_value=logs),
            ):
                response = self.client.get("/members/42/ingots/transactions")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("discord_id", body["data"])
        txs = body["data"]["transactions"]
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0]["change_type"], "ADD_INGOTS")
        self.assertEqual(
            txs[0]["admin"],
            {
                "id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                "discord_id": 7,
                "nickname": "mod",
            },
        )
        self.assertIsNone(txs[1]["admin"])
        self.assertNotIn("admin_name", txs[0])

    async def test_passes_days_param(self):
        member = _make_member(discord_id=42)
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_id_or_discord",
            new=AsyncMock(return_value=member),
        ):
            with patch(
                "ironforgedcore.services.changelog_service.ChangelogService.latest_ingot_transactions",
                new=AsyncMock(return_value=[]),
            ) as mock_tx:
                response = self.client.get("/members/42/ingots/transactions?days=30")

        self.assertEqual(response.status_code, 200)
        args, kwargs = mock_tx.call_args
        self.assertEqual(kwargs.get("discord_id"), 42)
        self.assertEqual(kwargs.get("days"), 30)
        self.assertIsNone(kwargs.get("after"))

    async def test_rejects_excessive_days(self):
        response = self.client.get("/members/42/ingots/transactions?days=10000")
        self.assertEqual(response.status_code, 422)

    def test_perm_denied_403(self):
        from api.routers.ingots import router

        consumer = make_consumer(perms=["ingots:read"])
        client = build_test_client(self.app, self.session, consumer)
        response = client.get("/members/42/ingots/transactions")
        self.assertEqual(response.status_code, 403)
