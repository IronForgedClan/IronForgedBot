import unittest
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.commands.trickortreat.outcomes import steal
from ironforgedbot.commands.trickortreat.outcomes.steal import (
    StealTargetView,
    _calculate_steal_penalty,
    _get_steal_success_rate,
)
from ironforgedbot.commands.trickortreat.types import IngotAdjustment
from ironforgedbot.services.trick_or_treat_service import TrickOrTreatTransferResponse
from ironforgedcore.common.ranks import RANK
from ironforgedcore.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    setup_database_service_mocks,
)

THRESHOLD_MIN = 25_000
THRESHOLD_START = 25_001
THRESHOLD_MAX = 3_000_000


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

        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )
        candidates = [
            create_test_db_member(
                nickname=f"Eligible{index}",
                discord_id=9000 + index,
                ingots=THRESHOLD_MIN + index,
                is_prospect=True,
            )
            for index in range(5)
        ]
        candidates.extend(
            [
                create_test_db_member(
                    nickname="Caller",
                    discord_id=self.test_user.id,
                    ingots=100_000,
                ),
                create_test_db_member(
                    nickname="Inactive",
                    discord_id=9100,
                    ingots=100_000,
                    active=False,
                ),
                create_test_db_member(
                    nickname="BelowMinimum",
                    discord_id=9101,
                    ingots=THRESHOLD_MIN - 1,
                ),
            ]
        )
        mock_steal_ms.get_all_active_members = AsyncMock(return_value=candidates)

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10_000,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(return_value=test_member)
        self.interaction.guild.members = []

        await steal.result_steal(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])
        target_labels = {
            child.label for child in call_kwargs["view"].children if child.row == 0
        }
        self.assertEqual(len(target_labels), 4)
        self.assertTrue(
            target_labels.issubset({member.nickname for member in candidates[:5]})
        )
        mock_steal_ms.get_all_active_members.assert_awaited_once_with()

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_result_steal_no_targets(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test steal when no active database targets meet balance minimum."""
        handler = create_test_trick_or_treat_handler()
        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )
        mock_steal_ms.get_all_active_members = AsyncMock(return_value=[])

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

        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )
        mock_steal_ms.get_all_active_members = AsyncMock(
            return_value=[
                create_test_db_member(
                    nickname="MemberUser", discord_id=9000, ingots=THRESHOLD_MIN
                )
            ]
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(return_value=test_member)
        self.interaction.guild.members = []

        await steal.result_steal(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("need", embed.description.lower())

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    @patch(
        "ironforgedbot.commands.trickortreat.outcomes.steal.create_trick_or_treat_service"
    )
    async def test_process_steal_success(
        self, mock_create_service, mock_member_service_class, mock_db
    ):
        """Test successful steal (25% chance)."""
        handler = create_test_trick_or_treat_handler()

        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=9001,
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
            if discord_id == target_db_member.discord_id:
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

        handler._get_user_info = AsyncMock(return_value=("TestUser", 2000))
        mock_transfer_service = AsyncMock()
        mock_transfer_service.transfer_ingots.return_value = (
            TrickOrTreatTransferResponse(
                status=True,
                message="Transfer completed",
                amount=1000,
                source_total=99_000,
                target_total=3000,
            )
        )
        mock_create_service.return_value = mock_transfer_service

        success_rate = _get_steal_success_rate(100_000)
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=success_rate - 0.1,
        ):
            result = await steal.process_steal(
                handler, self.interaction, 1000, target_db_member
            )

        mock_transfer_service.transfer_ingots.assert_awaited_once_with(
            target_db_member.discord_id,
            self.test_user.id,
            1000,
            "Trick or treat: stolen by TestUser",
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)
        self.assertIn("success", result.description.lower())

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    @patch(
        "ironforgedbot.commands.trickortreat.outcomes.steal.create_trick_or_treat_service"
    )
    async def test_process_steal_transfer_failure_does_not_credit_thief(
        self, mock_create_service, mock_member_service_class, mock_db
    ):
        handler = create_test_trick_or_treat_handler()
        handler._get_user_info = AsyncMock(return_value=("TestUser", 2000))
        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=9001,
            rank=RANK.IRON,
            ingots=100_000,
        )
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=target_db_member
        )
        mock_member_service_class.return_value = mock_member_service
        mock_db.get_session.return_value.__aenter__.return_value = AsyncMock()
        transfer_service = AsyncMock()
        transfer_service.transfer_ingots.return_value = TrickOrTreatTransferResponse(
            status=False,
            message="Insufficient balance",
            amount=0,
            source_total=0,
            target_total=0,
        )
        mock_create_service.return_value = transfer_service

        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=0,
        ):
            result = await steal.process_steal(
                handler, self.interaction, 1000, target_db_member
            )

        transfer_service.transfer_ingots.assert_awaited_once()
        self.assertIn("error", result.description.lower())

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_failure_reports_capped_penalty(
        self, mock_member_service_class, mock_db
    ):
        """Test failed steal reports amount actually removed from thief."""
        handler = create_test_trick_or_treat_handler()

        user_db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=500,
        )
        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=9001,
            rank=RANK.IRON,
            ingots=100_000,
        )

        def get_member_side_effect(discord_id):
            if discord_id == target_db_member.discord_id:
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

        handler._adjust_ingots = AsyncMock(return_value=IngotAdjustment(0, -500))
        handler._get_user_info = AsyncMock(return_value=("TestUser", 0))

        success_rate = _get_steal_success_rate(100_000)
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=success_rate + 0.1,
        ):
            result = await steal.process_steal(
                handler, self.interaction, 1000, target_db_member
            )

        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args[0]
        self.assertEqual(call_args[1], -800)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)
        self.assertIn("fail", result.description.lower())
        self.assertIn("-500", result.description)
        self.assertNotIn("-800", result.description)

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_target_below_minimum_is_ineligible(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test stale targets below the balance minimum cannot be stolen from."""
        handler = create_test_trick_or_treat_handler()

        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )

        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=9001,
            rank=RANK.IRON,
            ingots=THRESHOLD_MIN - 1,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(
            return_value=target_db_member
        )

        success_rate = _get_steal_success_rate(100_000)
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=success_rate - 0.1,
        ):
            result = await steal.process_steal(
                handler, self.interaction, 1000, target_db_member
            )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, discord.Embed)
        self.assertIn("eligible", result.description.lower())

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_inactive_target_is_ineligible(
        self, mock_steal_member_service, mock_steal_db
    ):
        handler = create_test_trick_or_treat_handler()
        _, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )
        target_db_member = create_test_db_member(
            nickname="InactiveTarget",
            discord_id=9001,
            ingots=100_000,
            active=False,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(
            return_value=target_db_member
        )
        handler._adjust_ingots = AsyncMock()

        result = await steal.process_steal(
            handler, self.interaction, 1000, target_db_member
        )

        self.assertIn("eligible", result.description.lower())
        handler._adjust_ingots.assert_not_awaited()

    async def test_steal_success_rate_scales_linearly_with_balance(self):
        """Test success odds increase smoothly from 10% to the 60% cap."""
        self.assertEqual(_get_steal_success_rate(THRESHOLD_MIN - 1), 0)
        self.assertEqual(_get_steal_success_rate(THRESHOLD_MIN), 0.10)
        self.assertEqual(_get_steal_success_rate(THRESHOLD_START), 0.10)
        self.assertAlmostEqual(_get_steal_success_rate(1_512_500), 0.35, places=5)
        self.assertEqual(_get_steal_success_rate(THRESHOLD_MAX), 0.60)
        self.assertEqual(_get_steal_success_rate(10_000_000), 0.60)

    async def test_steal_success_rate_range(self):
        """Test that all rates are valid probabilities (0.0-1.0)."""
        test_amounts = [
            0,
            THRESHOLD_MIN - 1,
            THRESHOLD_MIN,
            THRESHOLD_START,
            100_000,
            500_000,
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

        targets = [create_test_db_member("Target1", discord_id=9001, ingots=25_000)]
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

        targets = [create_test_db_member("Target1", discord_id=9001, ingots=25_000)]
        view = StealTargetView(handler, self.test_user.id, 1000, targets)
        view.message = AsyncMock()

        await view._walk_away_callback(self.interaction)

        self.interaction.response.defer.assert_called_once()
        view.message.edit.assert_called_once()

        edit_call_kwargs = view.message.edit.call_args.kwargs
        self.assertIn("embed", edit_call_kwargs)
        embed = edit_call_kwargs["embed"]
        self.assertIn("walk", embed.description.lower())

    async def test_steal_callback_disables_controls_when_processing_fails(self):
        handler = create_test_trick_or_treat_handler()
        target = create_test_db_member("Target", discord_id=9001, ingots=25_000)
        view = StealTargetView(handler, self.test_user.id, 1000, [target])
        view.message = AsyncMock()

        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.process_steal",
            side_effect=RuntimeError("database unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                await view.children[0].callback(self.interaction)

        self.assertIsNone(view.handler)
        view.message.edit.assert_awaited_with(view=None)
