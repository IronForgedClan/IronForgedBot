"""Tests for the steal outcome in trick-or-treat."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.commands.trickortreat.outcomes import steal
from ironforgedbot.commands.trickortreat.outcomes.steal import (
    StealTargetView,
    _calculate_steal_penalty,
    _get_steal_success_rate,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    MOCK_TRICK_OR_TREAT_DATA,
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    create_test_trick_or_treat_handler,
    setup_database_service_mocks,
)


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

        # Create mock Member role members
        member = create_test_member("MemberUser", [ROLE.MEMBER])
        self.interaction.guild.members = [self.test_user, member]

        mock_steal_db_session, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10000,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        await steal.result_steal(handler, self.interaction)

        # Verify a view was sent (has buttons)
        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.trickortreat.trick_or_treat_handler.MemberService")
    async def test_result_steal_no_targets(
        self, mock_member_service_class, mock_db
    ):
        """Test steal when no members with Member role available."""
        handler = create_test_trick_or_treat_handler()

        # No members with Member role (only the user)
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

        mock_steal_db_session, mock_steal_ms = setup_database_service_mocks(
            mock_steal_db, mock_steal_member_service
        )

        # User has very few ingots
        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10,
        )
        mock_steal_ms.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

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
            ingots=100_000,  # Gives 25% success rate
        )
        thief_db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2000,
        )

        # steal module will call get_member for both target and thief
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

        # Mock db.get_session to return a mock session
        mock_db.get_session.return_value.__aenter__.return_value = AsyncMock()

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=3000)
        # Mock _get_user_info to return nickname and ingots
        handler._get_user_info = AsyncMock(return_value=("TestUser", 2000))

        # Mock random to always succeed
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=0.2,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        # Should remove from target and add to user (2 calls to _adjust_ingots)
        self.assertEqual(handler._adjust_ingots.call_count, 2)
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_failure(self, mock_member_service_class, mock_db):
        """Test failed steal (75% chance, user loses penalty)."""
        handler = create_test_trick_or_treat_handler()

        target_member = create_test_member("TargetUser", [ROLE.MEMBER])

        # User member with enough ingots
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
            ingots=100_000,  # Gives 25% success rate
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

        # Mock db.get_session to return a mock session
        mock_db.get_session.return_value.__aenter__.return_value = AsyncMock()

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=200)
        # Mock _get_user_info to return nickname and ingots
        handler._get_user_info = AsyncMock(return_value=("TestUser", 1000))

        # Mock random to always fail
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=0.7,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        # Should only remove penalty from user (one call to _adjust_ingots with negative amount)
        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args[0]
        self.assertEqual(call_args[1], -800)  # 3/4 of 1000 = 750, rounds up to nearest 100 = 800
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.db")
    @patch("ironforgedbot.commands.trickortreat.outcomes.steal.MemberService")
    async def test_process_steal_target_has_zero_ingots(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test steal when target has no ingots."""
        handler = create_test_trick_or_treat_handler()

        target_member = create_test_member("TargetUser", [ROLE.MEMBER])

        mock_steal_db_session, mock_steal_ms = setup_database_service_mocks(
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

        # Mock random to succeed
        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.steal.random.random",
            return_value=0.2,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no ingots", embed.description.lower())

    # Success Rate Tier Tests
    async def test_steal_success_rate_under_25k(self):
        """Test steal success rate is 0% for targets with < 25k ingots."""
        self.assertEqual(_get_steal_success_rate(0), 0.0)
        self.assertEqual(_get_steal_success_rate(24_999), 0.0)

    async def test_steal_success_rate_25k_to_50k(self):
        """Test steal success rate is 5% for targets with 25k-50k ingots."""
        self.assertEqual(_get_steal_success_rate(25_000), 0.05)
        self.assertEqual(_get_steal_success_rate(49_999), 0.05)

    async def test_steal_success_rate_50k_to_100k(self):
        """Test steal success rate is 25% for targets with 50k-100k ingots."""
        self.assertEqual(_get_steal_success_rate(50_000), 0.25)
        self.assertEqual(_get_steal_success_rate(99_999), 0.25)

    async def test_steal_success_rate_100k_to_250k(self):
        """Test steal success rate is 30% for targets with 100k-250k ingots."""
        self.assertEqual(_get_steal_success_rate(100_000), 0.30)
        self.assertEqual(_get_steal_success_rate(249_999), 0.30)

    async def test_steal_success_rate_250k_to_500k(self):
        """Test steal success rate is 35% for targets with 250k-500k ingots."""
        self.assertEqual(_get_steal_success_rate(250_000), 0.35)
        self.assertEqual(_get_steal_success_rate(499_999), 0.35)

    async def test_steal_success_rate_500k_to_2m(self):
        """Test steal success rate is 40% for targets with 500k-2M ingots."""
        self.assertEqual(_get_steal_success_rate(500_000), 0.40)
        self.assertEqual(_get_steal_success_rate(1_999_999), 0.40)

    async def test_steal_success_rate_over_2m(self):
        """Test steal success rate is 45% for targets with 2M+ ingots."""
        self.assertEqual(_get_steal_success_rate(2_000_000), 0.45)
        self.assertEqual(_get_steal_success_rate(10_000_000), 0.45)

    # Penalty Calculation Tests
    async def test_steal_penalty_calculation(self):
        """Test that steal penalty is calculated as 3/4 rounded up to nearest 100."""
        # 3/4 of 1000 = 750, rounds up to 800
        self.assertEqual(_calculate_steal_penalty(1000), 800)

        # 3/4 of 1500 = 1125, rounds up to 1200
        self.assertEqual(_calculate_steal_penalty(1500), 1200)

        # 3/4 of 100 = 75, rounds up to 100
        self.assertEqual(_calculate_steal_penalty(100), 100)

        # 3/4 of 2000 = 1500, already multiple of 100
        self.assertEqual(_calculate_steal_penalty(2000), 1500)

        # Edge case: 3/4 of 1 = 1 (rounds up), then rounds to 100
        self.assertEqual(_calculate_steal_penalty(1), 100)

    # View Timeout Tests
    async def test_steal_view_timeout(self):
        """Test that steal view times out correctly after 45 seconds."""
        handler = create_test_trick_or_treat_handler()

        targets = [create_test_member("Target1", [ROLE.MEMBER])]
        view = StealTargetView(handler, self.test_user.id, 1000, targets)
        view.message = AsyncMock()

        # Simulate timeout
        await view.on_timeout()

        # Should clear items and edit message
        self.assertEqual(len(view.children), 0)
        view.message.edit.assert_called_once()
        embed = view.message.edit.call_args.kwargs["embed"]
        self.assertIn("time", embed.description.lower())

    # Walk Away Tests
    async def test_steal_walk_away(self):
        """Test that walk away button works correctly."""
        handler = create_test_trick_or_treat_handler()

        targets = [create_test_member("Target1", [ROLE.MEMBER])]
        view = StealTargetView(handler, self.test_user.id, 1000, targets)
        view.message = AsyncMock()

        # Simulate walk away button click
        await view._walk_away_callback(self.interaction)

        # Should defer and delete message
        self.interaction.response.defer.assert_called_once()
        view.message.delete.assert_called_once()

        # Should send walk away message
        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("walked", embed.description.lower())
