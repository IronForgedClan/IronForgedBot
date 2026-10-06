import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.trickortreat.outcomes import jackpot
from ironforgedbot.commands.trickortreat.types import (
    IngotAdjustment,
    IngotAdjustmentFailure,
)
from ironforgedcore.common.ranks import RANK
from ironforgedcore.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    setup_database_service_mocks,
)


class TestJackpotOutcome(unittest.IsolatedAsyncioTestCase):
    """Test cases for jackpot outcome functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    @patch("ironforgedbot.commands.trickortreat.outcomes.jackpot.STATE")
    async def test_result_jackpot_already_claimed(self, mock_state):
        """Test that jackpot shows consolation message when already claimed."""
        handler = create_test_trick_or_treat_handler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": True}

        await jackpot.result_jackpot(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("already claimed", embed.description.lower())

    @patch("ironforgedcore.database.db")
    @patch("ironforgedcore.services.member_service.MemberService")
    @patch("ironforgedbot.commands.trickortreat.outcomes.jackpot.STATE")
    async def test_result_jackpot_success(
        self, mock_state, mock_member_service_class, mock_db
    ):
        """Test successful jackpot claim."""
        handler = create_test_trick_or_treat_handler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": False}

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=500_000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        handler._adjust_ingots = AsyncMock(
            return_value=IngotAdjustment(1_500_000, 1_000_000)
        )
        handler._get_user_info = AsyncMock(return_value=("TestUser", 500_000))

        await jackpot.result_jackpot(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("jackpot", embed.description.lower())
        self.assertTrue(mock_state.state["trick_or_treat_jackpot_claimed"])

    @patch("ironforgedbot.commands.trickortreat.outcomes.jackpot.STATE")
    async def test_result_jackpot_does_not_claim_when_award_fails(self, mock_state):
        handler = create_test_trick_or_treat_handler()
        mock_state.state = {"trick_or_treat_jackpot_claimed": False}
        handler._adjust_ingots = AsyncMock(
            return_value=IngotAdjustment(None, 0, IngotAdjustmentFailure.ERROR)
        )
        handler._get_user_info = AsyncMock(return_value=("TestUser", 0))

        await jackpot.result_jackpot(handler, self.interaction)

        self.assertFalse(mock_state.state["trick_or_treat_jackpot_claimed"])

    @patch("ironforgedbot.commands.trickortreat.outcomes.jackpot.STATE")
    async def test_result_jackpot_serializes_concurrent_claims(self, mock_state):
        handler = create_test_trick_or_treat_handler()
        mock_state.state = {"trick_or_treat_jackpot_claimed": False}
        adjustment_started = asyncio.Event()
        finish_adjustment = asyncio.Event()

        async def adjust_ingots(*args, **kwargs):
            adjustment_started.set()
            await finish_adjustment.wait()
            return IngotAdjustment(1500, 500)

        handler._adjust_ingots = AsyncMock(side_effect=adjust_ingots)
        handler._get_user_info = AsyncMock(return_value=("TestUser", 1500))

        first_claim = asyncio.create_task(
            jackpot.result_jackpot(handler, self.interaction)
        )
        await adjustment_started.wait()
        second_claim = asyncio.create_task(
            jackpot.result_jackpot(handler, self.interaction)
        )
        await asyncio.sleep(0)
        finish_adjustment.set()
        await asyncio.gather(first_claim, second_claim)

        handler._adjust_ingots.assert_awaited_once()
        self.assertTrue(mock_state.state["trick_or_treat_jackpot_claimed"])
