import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.trickortreat.outcomes import steal
from ironforgedbot.commands.trickortreat.outcomes.steal import (
    StealTargetView,
    _calculate_steal_penalty,
    _get_steal_success_rate,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    setup_database_service_mocks,
)

THRESHOLD_MIN = 25_000
THRESHOLD_LOW = 50_000
THRESHOLD_MID = 100_000
THRESHOLD_HIGH = 250_000
THRESHOLD_VERY_HIGH = 500_000
THRESHOLD_MAX = 2_000_000


class TestStealOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for steal outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_result_steal_creates_view_with_buttons(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test that steal creates an offer with target buttons and walk away."""
        handler = create_test_trick_or_treat_handler()

        member = create_test_member("MemberUser", [ROLE.MEMBER])
        self.interaction.guild.members = [self.test_user, member]

        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10_000,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(return_value=test_member)

        await steal.result_steal(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

    async def test_result_steal_no_targets(self):
        """Test steal when no members with Member role available."""
        handler = create_test_trick_or_treat_handler()

        self.interaction.guild.members = [self.test_user]

        await steal.result_steal(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no targets", embed.description.lower())

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_result_steal_user_insufficient_ingots(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test steal when user doesn't have enough ingots for penalty."""
        handler = create_test_trick_or_treat_handler()

        member = create_test_member("MemberUser", [ROLE.MEMBER])
        self.interaction.guild.members = [self.test_user, member]

        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(return_value=test_member)

        await steal.result_steal(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("need", embed.description.lower())

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_success(self, mock_member_service_class, mock_db):
        """Test successful steal (25% chance)."""
        handler = create_test_trick_or_treat_handler()

        target_member = create_test_member("TargetUser", [ROLE.MEMBER])

        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=target_member.id,
            rank=RANK.IRON,
            ingots=100_000,
        )
        thief_db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2000,
        )

        def get_member_side_effect(discord_id):
            if discord_id == target_member.id:
                return target_db_member
            elif discord_id == self.test_user.id:
                return thief_db_member
            return None

        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = AsyncMock(
            side_effect=get_member_side_effect
        )
        mock_member_service_class.return_value = mock_member_service

        mock_db.get_session.return_value.__aenter__.return_value = AsyncMock()

        handler._adjust_ingots = AsyncMock(return_value=3000)
        handler._get_user_info = AsyncMock(return_value=("TestUser", 2000))

        success_rate = _get_steal_success_rate(100_000)
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=success_rate - 0.1,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        self.assertEqual(handler._adjust_ingots.call_count, 2)
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_failure(self, mock_member_service_class, mock_db):
        """Test failed steal."""
        handler = create_test_trick_or_treat_handler()

        target_member = create_test_member("TargetUser", [ROLE.MEMBER])

        user_db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1000,
        )
        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=target_member.id,
            rank=RANK.IRON,
            ingots=100_000,
        )

        def get_member_side_effect(discord_id):
            if discord_id == target_member.id:
                return target_db_member
            elif discord_id == self.test_user.id:
                return user_db_member
            return None

        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = AsyncMock(
            side_effect=get_member_side_effect
        )
        mock_member_service_class.return_value = mock_member_service

        mock_db.get_session.return_value.__aenter__.return_value = AsyncMock()

        handler._adjust_ingots = AsyncMock(return_value=200)
        handler._get_user_info = AsyncMock(return_value=("TestUser", 1000))

        success_rate = _get_steal_success_rate(100_000)
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=success_rate + 0.1,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args[0]
        self.assertEqual(call_args[1], -800)
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_target_has_zero_ingots(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test steal when target has no ingots."""
        handler = create_test_trick_or_treat_handler()

        target_member = create_test_member("TargetUser", [ROLE.MEMBER])

        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )

        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=target_member.id,
            rank=RANK.IRON,
            ingots=0,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(
            return_value=target_db_member
        )

        success_rate = _get_steal_success_rate(100_000)
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=success_rate - 0.1,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no ingots", embed.description.lower())

    async def test_steal_success_rate_increases_with_wealth(self):
        """Test that success rate increases as target wealth increases."""
        rate_under_min = _get_steal_success_rate(THRESHOLD_MIN - 1)
        rate_low = _get_steal_success_rate(THRESHOLD_LOW)
        rate_mid = _get_steal_success_rate(THRESHOLD_MID)
        rate_high = _get_steal_success_rate(THRESHOLD_HIGH)
        rate_very_high = _get_steal_success_rate(THRESHOLD_VERY_HIGH)
        rate_max = _get_steal_success_rate(THRESHOLD_MAX)

        self.assertLessEqual(rate_under_min, rate_low)
        self.assertLess(rate_low, rate_mid)
        self.assertLess(rate_mid, rate_high)
        self.assertLess(rate_high, rate_very_high)
        self.assertLess(rate_very_high, rate_max)

    async def test_steal_success_rate_boundaries(self):
        """Test that rates are consistent within brackets and change at boundaries."""
        self.assertEqual(
            _get_steal_success_rate(THRESHOLD_MIN),
            _get_steal_success_rate(THRESHOLD_LOW - 1),
        )
        self.assertEqual(
            _get_steal_success_rate(THRESHOLD_MID),
            _get_steal_success_rate(THRESHOLD_HIGH - 1),
        )

        self.assertNotEqual(
            _get_steal_success_rate(THRESHOLD_LOW - 1),
            _get_steal_success_rate(THRESHOLD_LOW),
        )
        self.assertNotEqual(
            _get_steal_success_rate(THRESHOLD_HIGH - 1),
            _get_steal_success_rate(THRESHOLD_HIGH),
        )

    async def test_steal_success_rate_range(self):
        """Test that all rates are valid probabilities (0.0-1.0)."""
        test_amounts = [
            0,
            THRESHOLD_MIN - 1,
            THRESHOLD_MIN,
            THRESHOLD_LOW,
            THRESHOLD_MID,
            THRESHOLD_HIGH,
            THRESHOLD_VERY_HIGH,
            THRESHOLD_MAX,
            10_000_000,
        ]

        for amount in test_amounts:
            rate = _get_steal_success_rate(amount)
            self.assertGreaterEqual(
                rate, 0.0, f"Rate for {amount:,} ingots is below 0.0"
            )
            self.assertLessEqual(rate, 1.0, f"Rate for {amount:,} ingots is above 1.0")

    async def test_steal_penalty_calculation(self):
        """Test that steal penalty is calculated as 3/4 rounded up to nearest 100."""
        self.assertEqual(_calculate_steal_penalty(1000), 800)
        self.assertEqual(_calculate_steal_penalty(1500), 1200)
        self.assertEqual(_calculate_steal_penalty(100), 100)
        self.assertEqual(_calculate_steal_penalty(2000), 1500)
        self.assertEqual(_calculate_steal_penalty(1), 100)

    async def test_steal_view_timeout(self):
        """Test that steal view times out correctly after 45 seconds."""
        handler = create_test_trick_or_treat_handler()

        targets = [create_test_member("Target1", [ROLE.MEMBER])]
        view = StealTargetView(handler, self.test_user.id, 1000, targets)
        view.message = AsyncMock()

        await view.on_timeout()

        self.assertEqual(len(view.children), 0)
        view.message.edit.assert_called_once()
        embed = view.message.edit.call_args.kwargs["embed"]
        self.assertIn("time", embed.description.lower())

    async def test_steal_walk_away(self):
        """Test that walk away button works correctly."""
        handler = create_test_trick_or_treat_handler()

        targets = [create_test_member("Target1", [ROLE.MEMBER])]
        view = StealTargetView(handler, self.test_user.id, 1000, targets)
        view.message = AsyncMock()

        await view._walk_away_callback(self.interaction)

        self.interaction.response.defer.assert_called_once()
        view.message.delete.assert_called_once()

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("walked", embed.description.lower())
