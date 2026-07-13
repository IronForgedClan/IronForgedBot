import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedcore.common.ranks import RANK
from ironforgedcore.models import Member
from ironforgedcore.models.score import ActivityScore, ScoreBreakdown, SkillScore
from ironforgedcore.services.member_service import MemberNotFoundException

from api.schemas.score import ScoreHistoryQueryParams

from tests.api_tests.helpers import build_test_app, build_test_client, make_consumer


def _make_skill(name: str, points: int) -> SkillScore:
    return SkillScore(
        name=name,
        display_name=None,
        display_order=0,
        emoji_key="emoji",
        level=99,
        xp=13_034_431,
        points=points,
    )


def _make_activity(name: str, kc: int, points: int) -> ActivityScore:
    return ActivityScore(
        name=name,
        display_name=None,
        display_order=0,
        emoji_key="emoji",
        kc=kc,
        points=points,
    )


def _make_breakdown() -> ScoreBreakdown:
    return ScoreBreakdown(
        skills=[_make_skill("Attack", 100), _make_skill("Strength", 150)],
        clues=[_make_activity("Clue Scroll (all)", 50, 25)],
        raids=[_make_activity("Chambers of Xeric", 10, 75)],
        bosses=[_make_activity("Zulrah", 100, 50)],
    )


def _make_member_with_rsn(rsn: str = "zezima", discord_id: int = 12345) -> MagicMock:
    m = MagicMock(spec=Member)
    m.rsn = rsn
    m.discord_id = discord_id
    m.nickname = rsn
    return m


class TestGetPlayerScore(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.scores import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["scores:read"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    async def test_returns_player_score(self):
        breakdown = _make_breakdown()
        with patch(
            "ironforgedbot.services.score_service.get_score_service"
        ) as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.get_player_score = AsyncMock(return_value=breakdown)
            mock_get_svc.return_value = mock_svc

            response = self.client.get("/players/zezima/score")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["player_name"], "zezima")
        self.assertEqual(body["data"]["total_points"], 100 + 150 + 25 + 75 + 50)
        self.assertEqual(len(body["data"]["skills"]), 2)
        self.assertEqual(len(body["data"]["clues"]), 1)
        self.assertEqual(len(body["data"]["raids"]), 1)
        self.assertEqual(len(body["data"]["bosses"]), 1)

    async def test_hiscores_not_found_404(self):
        from ironforgedcore.exceptions.score_exceptions import HiscoresNotFound

        with patch(
            "ironforgedbot.services.score_service.get_score_service"
        ) as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.get_player_score = AsyncMock(side_effect=HiscoresNotFound())
            mock_get_svc.return_value = mock_svc

            response = self.client.get("/players/nonexistent/score")

        self.assertEqual(response.status_code, 404)

    def test_rejects_long_name(self):
        response = self.client.get("/players/thisnameistoolongforrunescape/score")
        self.assertEqual(response.status_code, 400)

    def test_perm_denied_403(self):
        from api.routers.scores import router

        consumer = make_consumer(perms=["members:read"])
        client = build_test_client(self.app, self.session, consumer)
        response = client.get("/players/zezima/score")
        self.assertEqual(response.status_code, 403)


class TestGetPlayerScoreHistory(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from api.routers.scores import router

        self.session = AsyncMock(spec=AsyncSession)
        self.consumer = make_consumer(perms=["scores:read:history"])
        self.app = build_test_app(include_routers=[router])
        self.client = build_test_client(self.app, self.session, self.consumer)

    async def test_returns_history(self):
        member = _make_member_with_rsn()
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_rsn",
            new=AsyncMock(return_value=member),
        ):
            with patch(
                "ironforgedcore.services.score_history_service.ScoreHistoryService.get_score_history",
                new=AsyncMock(return_value={7: 100, 30: 200, 90: None}),
            ):
                response = self.client.get("/players/zezima/score-history?days=7,30,90")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["discord_id"], 12345)
        self.assertEqual(len(body["data"]["entries"]), 3)

    async def test_member_not_found_404(self):
        with patch(
            "ironforgedcore.services.member_service.MemberService.get_member_by_rsn_or_raise",
            new=AsyncMock(
                side_effect=MemberNotFoundException("No member with rsn=ghost")
            ),
        ):
            response = self.client.get("/players/ghost/score-history?days=7")

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error"]["code"], "not_found")
        self.assertEqual(body["error"]["message"], "No member with rsn=ghost")

    def test_rejects_invalid_days(self):
        response = self.client.get("/players/zezima/score-history?days=abc")
        self.assertEqual(response.status_code, 400)

    def test_rejects_out_of_range_days(self):
        response = self.client.get("/players/zezima/score-history?days=1000")
        self.assertEqual(response.status_code, 400)

    def test_perm_denied_403(self):
        from api.routers.scores import router

        consumer = make_consumer(perms=["scores:read"])
        client = build_test_client(self.app, self.session, consumer)
        response = client.get("/players/zezima/score-history?days=7")
        self.assertEqual(response.status_code, 403)


class TestScoreHistoryQueryParams(unittest.TestCase):
    def test_default_periods(self):
        params = ScoreHistoryQueryParams.parse("7,30,90")
        self.assertEqual(params.periods, [7, 30, 90])

    def test_single_period(self):
        params = ScoreHistoryQueryParams.parse("7")
        self.assertEqual(params.periods, [7])

    def test_strips_whitespace(self):
        params = ScoreHistoryQueryParams.parse(" 7 , 30 , 90 ")
        self.assertEqual(params.periods, [7, 30, 90])

    def test_rejects_non_integer(self):
        with self.assertRaises(ValueError) as ctx:
            ScoreHistoryQueryParams.parse("abc")
        self.assertIn("comma-separated integers", str(ctx.exception))

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError) as ctx:
            ScoreHistoryQueryParams.parse("1000")
        self.assertIn("between 1 and 365", str(ctx.exception))

    def test_rejects_zero(self):
        with self.assertRaises(ValueError):
            ScoreHistoryQueryParams.parse("0")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            ScoreHistoryQueryParams.parse(",")

    def test_default_constructor(self):
        params = ScoreHistoryQueryParams()
        self.assertEqual(params.periods, [7, 30, 90])
