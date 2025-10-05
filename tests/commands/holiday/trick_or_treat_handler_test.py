import asyncio
import json
import unittest
from typing import Counter
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import discord

from ironforgedbot.commands.holiday.outcomes import (
    double_or_nothing,
    ingot_changes,
    jackpot,
    steal,
)
from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    HIGH_INGOT_MAX,
    HIGH_INGOT_MIN,
    LOW_INGOT_MAX,
    LOW_INGOT_MIN,
    TrickOrTreat,
)
from ironforgedbot.commands.holiday.trick_or_treat_handler import (
    TrickOrTreatHandler,
)
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    get_url_status_code,
    setup_database_service_mocks,
)

# Mock data for tests
MOCK_TRICK_OR_TREAT_DATA = json.dumps({
    "GENERAL": {
        "POSITIVE_MESSAGES": ["Test positive {ingots}"],
        "NEGATIVE_MESSAGES": ["Test negative {ingots}"],
        "NEGATIVE_ANNOYANCES": ["bud"],
        "NO_INGOTS_MESSAGE": "No ingots test message"
    },
    "JACKPOT": {
        "SUCCESS_PREFIX": "Jackpot {mention} {ingot_icon}{amount:,}",
        "CLAIMED_MESSAGE": "Already claimed"
    },
    "REMOVE_ALL_TRICK": {
        "MESSAGE": "Removed {ingot_icon}-{amount:,}"
    },
    "DOUBLE_OR_NOTHING": {
        "OFFER": "Double or nothing {ingot_icon}{amount:,} expires {expires}",
        "WIN": "You won {ingot_icon}{total_amount:,}",
        "LOSE": "You lost {ingot_icon}{amount:,}",
        "KEEP": "You kept {ingot_icon}{amount:,}",
        "EXPIRED": "Expired {ingot_icon}{amount:,}"
    },
    "STEAL": {
        "OFFER": "Steal {ingot_icon}{amount:,} penalty {ingot_icon}{penalty:,} expires {expires}",
        "SUCCESS": "Success {ingot_icon}{amount:,} from {target_mention}",
        "FAILURE": "Failed {ingot_icon}{amount:,} {target_mention} penalty {ingot_icon}{penalty:,}",
        "WALK_AWAY": "Walked away",
        "EXPIRED": "Time's up",
        "NO_TARGETS": "No targets",
        "TARGET_NO_INGOTS": "{target_mention} has no ingots",
        "USER_NO_INGOTS": "Need {ingot_icon}{penalty:,}"
    },
    "JOKE": {
        "MESSAGES": ["Test joke"]
    },
    "MEDIA": {
        "GIFS": [],
        "THUMBNAILS": ["http://test.com/img.png"]
    }
})


class TestTrickOrTreatHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)
        self.interaction.guild = MagicMock()
        self.interaction.guild.get_member = MagicMock(return_value=self.test_user)

    async def test_init(self):
        """Test that TrickOrTreatHandler initializes with correct weights and empty history."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()
            expected_weights = [item.value for item in TrickOrTreat]

            self.assertEqual(handler.gif_history, [])
            self.assertEqual(handler.thumbnail_history, [])
            self.assertEqual(handler.positive_message_history, [])
            self.assertEqual(handler.negative_message_history, [])
            self.assertEqual(handler.weights, expected_weights)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_add_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successfully adding ingots to a player."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, _ = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 1500
        mock_ingot_service.try_add_ingots = AsyncMock(return_value=mock_result)

        result = await handler._adjust_ingots(self.interaction, 500, self.test_user)

        self.assertEqual(result, 1500)
        mock_ingot_service.try_add_ingots.assert_called_once_with(
            self.test_user.id, 500, None, "Trick or treat: win"
        )

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_remove_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successfully removing ingots from a player."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 500
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)

        result = await handler._adjust_ingots(self.interaction, -500, self.test_user)

        self.assertEqual(result, 500)
        mock_ingot_service.try_remove_ingots.assert_called_once()

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.send_error_response")
    async def test_adjust_ingots_member_has_zero_ingots(
        self,
        mock_send_error,
        mock_member_service_class,
        mock_ingot_service_class,
        mock_db,
    ):
        """Test that removing ingots from a player with 0 ingots returns None."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=0,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        result = await handler._adjust_ingots(self.interaction, -500, self.test_user)

        self.assertIsNone(result)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_adjust_ingots_caps_removal_at_balance(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test that trying to remove more ingots than balance only removes available amount."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )
        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=100,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 0
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)

        result = await handler._adjust_ingots(self.interaction, -500, self.test_user)

        # Should cap the removal at the member's balance
        mock_ingot_service.try_remove_ingots.assert_called_once_with(
            self.test_user.id, -100, None, "Trick or treat: loss"
        )
        self.assertEqual(result, 0)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_handle_ingot_result_positive(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test _handle_ingot_result with a positive outcome."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1500,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots to return a successful balance
        handler._adjust_ingots = AsyncMock(return_value=1500)

        await handler._handle_ingot_result(self.interaction, 500, is_positive=True)

        self.interaction.followup.send.assert_called_once()
        call_args = self.interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]
        self.assertIsNotNone(embed)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_handle_ingot_result_no_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test _handle_ingot_result when player has no ingots."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=0,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots to return None (no ingots)
        handler._adjust_ingots = AsyncMock(return_value=None)

        await handler._handle_ingot_result(self.interaction, -500, is_positive=False)

        self.interaction.followup.send.assert_called_once()

    async def test_result_add_low(self):
        """Test result_add_low generates correct ingot range."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        handler._handle_ingot_result = AsyncMock()

        await ingot_changes.result_add_low(handler, self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertGreaterEqual(quantity, LOW_INGOT_MIN)
        self.assertLess(quantity, LOW_INGOT_MAX)
        self.assertTrue(is_positive)

    async def test_result_remove_high(self):
        """Test result_remove_high generates correct ingot range."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        handler._handle_ingot_result = AsyncMock()

        await ingot_changes.result_remove_high(handler, self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertLessEqual(quantity, -HIGH_INGOT_MIN)
        self.assertGreater(quantity, -HIGH_INGOT_MAX)
        self.assertFalse(is_positive)

    @patch("ironforgedbot.commands.holiday.outcomes.jackpot.STATE")
    async def test_result_jackpot_already_claimed(self, mock_state):
        """Test that jackpot shows consolation message when already claimed."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": True}

        await jackpot.result_jackpot(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("already claimed", embed.description.lower())

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.jackpot.STATE")
    async def test_result_jackpot_success(self, mock_state, mock_member_service_class, mock_db):
        """Test successful jackpot claim."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": False}

        # Setup database mocks for jackpot module
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

        handler._adjust_ingots = AsyncMock(return_value=1_500_000)

        await jackpot.result_jackpot(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("jackpot", embed.description.lower())
        self.assertTrue(mock_state.state["trick_or_treat_jackpot_claimed"])

    async def test_unique_gifs(self):
        """Test that all GIFs in the data file are unique."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            GIFS = data["MEDIA"]["GIFS"]

        duplicates = [gif for gif, count in Counter(GIFS).items() if count > 1]
        assert not duplicates, f"Duplicate gifs: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_gifs_return_200(self):
        """Test that all GIF URLs are accessible (returns 200)."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            GIFS = data["MEDIA"]["GIFS"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in GIFS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(GIFS, results):
                assert result == 200, f"{url} returned status code {result}"

    async def test_unique_thumbnails(self):
        """Test that all thumbnails in the data file are unique."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            THUMBNAILS = data["MEDIA"]["THUMBNAILS"]

        duplicates = [gif for gif, count in Counter(THUMBNAILS).items() if count > 1]
        assert not duplicates, f"Duplicate thumbnails: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_thumbnails_return_200(self):
        """Test that all thumbnail URLs are accessible (returns 200)."""
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            THUMBNAILS = data["MEDIA"]["THUMBNAILS"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in THUMBNAILS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(THUMBNAILS, results):
                assert result == 200, f"{url} returned status code {result}"

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    @patch("ironforgedbot.commands.holiday.outcomes.double_or_nothing.STATE")
    async def test_result_double_or_nothing_creates_offer(
        self, mock_state, mock_member_service_class, mock_db
    ):
        """Test that double-or-nothing creates an offer with a button."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"double_or_nothing_offers": {}}

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1500,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=2000)

        await double_or_nothing.result_double_or_nothing(handler, self.interaction)

        # Verify ingots were added
        handler._adjust_ingots.assert_called_once()

        # Verify a view was sent (has the button)
        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

        # Verify offer was stored in state
        user_id_str = str(self.test_user.id)
        self.assertIn(user_id_str, mock_state.state["double_or_nothing_offers"])

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_process_double_or_nothing_win(
        self, mock_member_service_class, mock_db
    ):
        """Test processing a winning double-or-nothing gamble."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2500,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=3000)

        # Mock random to always win
        with patch("ironforgedbot.commands.holiday.outcomes.double_or_nothing.random.random", return_value=0.3):
            await double_or_nothing.process_double_or_nothing(handler, self.interaction, 500)

        # Should add the amount (winning)
        handler._adjust_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_process_double_or_nothing_lose(
        self, mock_member_service_class, mock_db
    ):
        """Test processing a losing double-or-nothing gamble."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        # Mock _adjust_ingots directly to avoid complex database mocking
        handler._adjust_ingots = AsyncMock(return_value=500)

        # Mock random to always lose
        with patch("ironforgedbot.commands.holiday.outcomes.double_or_nothing.random.random", return_value=0.7):
            await double_or_nothing.process_double_or_nothing(handler, self.interaction, 500)

        # Should remove the amount (losing)
        handler._adjust_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.outcomes.steal.db")
    @patch("ironforgedbot.commands.holiday.outcomes.steal.MemberService")
    async def test_result_steal_creates_view_with_buttons(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test that steal creates an offer with target buttons and walk away."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

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

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_result_steal_no_targets(
        self, mock_member_service_class, mock_db
    ):
        """Test steal when no members with Member role available."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # No members with Member role (only the user)
        self.interaction.guild.members = [self.test_user]

        await steal.result_steal(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no targets", embed.description.lower())

    @patch("ironforgedbot.commands.holiday.outcomes.steal.db")
    @patch("ironforgedbot.commands.holiday.outcomes.steal.MemberService")
    async def test_result_steal_user_insufficient_ingots(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test steal when user doesn't have enough ingots for penalty."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

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

    @patch("ironforgedbot.commands.holiday.outcomes.steal.db")
    @patch("ironforgedbot.commands.holiday.outcomes.steal.MemberService")
    async def test_process_steal_success(self, mock_member_service_class, mock_db):
        """Test successful steal (25% chance)."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

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

        # Mock random to always succeed
        with patch(
            "ironforgedbot.commands.holiday.outcomes.steal.random.random",
            return_value=0.2,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        # Should remove from target and add to user (2 calls to _adjust_ingots)
        self.assertEqual(handler._adjust_ingots.call_count, 2)
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.outcomes.steal.db")
    @patch("ironforgedbot.commands.holiday.outcomes.steal.MemberService")
    async def test_process_steal_failure(self, mock_member_service_class, mock_db):
        """Test failed steal (75% chance, user loses penalty)."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

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

        # Mock random to always fail
        with patch(
            "ironforgedbot.commands.holiday.outcomes.steal.random.random",
            return_value=0.7,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        # Should only remove penalty from user (one call to _adjust_ingots with negative amount)
        handler._adjust_ingots.assert_called_once()
        call_args = handler._adjust_ingots.call_args[0]
        self.assertEqual(call_args[1], -800)  # 3/4 of 1000 = 750, rounds up to nearest 100 = 800
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.outcomes.steal.db")
    @patch("ironforgedbot.commands.holiday.outcomes.steal.MemberService")
    async def test_process_steal_target_has_zero_ingots(
        self, mock_steal_member_service, mock_steal_db
    ):
        """Test steal when target has no ingots."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

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
            "ironforgedbot.commands.holiday.outcomes.steal.random.random",
            return_value=0.2,
        ):
            await steal.process_steal(handler, self.interaction, 1000, target_member)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no ingots", embed.description.lower())

    # === NEW COMPREHENSIVE TESTS ===

    # Double-or-Nothing Keep Callback Tests
    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_double_or_nothing_keep_callback(
        self, mock_member_service_class, mock_db
    ):
        """Test that keep winnings button works correctly."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        from ironforgedbot.commands.holiday.outcomes.double_or_nothing import (
            DoubleOrNothingView,
        )

        view = DoubleOrNothingView(handler, self.test_user.id, 500)
        view.message = AsyncMock()

        # Simulate keep button click
        await view._keep_callback(self.interaction)

        # Should defer and delete message
        self.interaction.response.defer.assert_called_once()
        view.message.delete.assert_called_once()

        # Should send keep message
        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("kept", embed.description.lower())

    # Double-or-Nothing Timeout Tests
    @patch("ironforgedbot.database.database.db")
    @patch("ironforgedbot.services.member_service.MemberService")
    async def test_double_or_nothing_timeout(
        self, mock_member_service_class, mock_db
    ):
        """Test that double-or-nothing view times out correctly."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=2000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        from ironforgedbot.commands.holiday.outcomes.double_or_nothing import (
            DoubleOrNothingView,
        )

        view = DoubleOrNothingView(handler, self.test_user.id, 500)
        view.message = AsyncMock()

        # Simulate timeout
        await view.on_timeout()

        # Should clear items and edit message
        self.assertEqual(len(view.children), 0)
        view.message.edit.assert_called_once()
        embed = view.message.edit.call_args.kwargs["embed"]
        self.assertIn("expired", embed.description.lower())

    # Steal Success Rate Tier Tests
    async def test_steal_success_rate_under_25k(self):
        """Test steal success rate is 0% for targets with < 25k ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(0), 0.0)
        self.assertEqual(_get_steal_success_rate(24_999), 0.0)

    async def test_steal_success_rate_25k_to_50k(self):
        """Test steal success rate is 5% for targets with 25k-50k ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(25_000), 0.05)
        self.assertEqual(_get_steal_success_rate(49_999), 0.05)

    async def test_steal_success_rate_50k_to_100k(self):
        """Test steal success rate is 25% for targets with 50k-100k ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(50_000), 0.25)
        self.assertEqual(_get_steal_success_rate(99_999), 0.25)

    async def test_steal_success_rate_100k_to_250k(self):
        """Test steal success rate is 30% for targets with 100k-250k ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(100_000), 0.30)
        self.assertEqual(_get_steal_success_rate(249_999), 0.30)

    async def test_steal_success_rate_250k_to_500k(self):
        """Test steal success rate is 35% for targets with 250k-500k ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(250_000), 0.35)
        self.assertEqual(_get_steal_success_rate(499_999), 0.35)

    async def test_steal_success_rate_500k_to_2m(self):
        """Test steal success rate is 40% for targets with 500k-2M ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(500_000), 0.40)
        self.assertEqual(_get_steal_success_rate(1_999_999), 0.40)

    async def test_steal_success_rate_over_2m(self):
        """Test steal success rate is 45% for targets with 2M+ ingots."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _get_steal_success_rate,
        )

        self.assertEqual(_get_steal_success_rate(2_000_000), 0.45)
        self.assertEqual(_get_steal_success_rate(10_000_000), 0.45)

    # Steal Penalty Calculation Tests
    async def test_steal_penalty_calculation(self):
        """Test that steal penalty is calculated as 3/4 rounded up to nearest 100."""
        from ironforgedbot.commands.holiday.outcomes.steal import (
            _calculate_steal_penalty,
        )

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

    # Steal Timeout Tests
    async def test_steal_view_timeout(self):
        """Test that steal view times out correctly after 45 seconds."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        from ironforgedbot.commands.holiday.outcomes.steal import StealTargetView

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

    # Steal Walk Away Tests
    async def test_steal_walk_away(self):
        """Test that walk away button works correctly."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        from ironforgedbot.commands.holiday.outcomes.steal import StealTargetView

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

    # Trick Outcome Tests
    @patch("ironforgedbot.commands.holiday.outcomes.trick.db")
    @patch("ironforgedbot.commands.holiday.outcomes.trick.MemberService")
    async def test_trick_remove_all_with_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test trick outcome when user has ingots (displays fake removal)."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=5000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        from ironforgedbot.commands.holiday.outcomes import trick

        await trick.result_remove_all_ingots_trick(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        # Should show the fake removal message
        self.assertIn("5", embed.description)

    @patch("ironforgedbot.commands.holiday.outcomes.trick.db")
    @patch("ironforgedbot.commands.holiday.outcomes.trick.MemberService")
    async def test_trick_remove_all_no_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test trick outcome when user has no ingots."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Setup database mocks
        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=0,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        from ironforgedbot.commands.holiday.outcomes import trick

        await trick.result_remove_all_ingots_trick(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        # Should show no ingots message
        self.assertIn("no ingots", embed.description.lower())

    # Joke Outcome Test
    async def test_joke_outcome(self):
        """Test that joke outcome sends a random joke."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        from ironforgedbot.commands.holiday.outcomes import joke

        await joke.result_joke(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIsNotNone(embed.description)

    # GIF Outcome Test
    async def test_gif_outcome(self):
        """Test that GIF outcome sends a GIF."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()
            # Add a GIF to the handler's list
            handler.GIFS = ["http://test.com/gif1.gif", "http://test.com/gif2.gif"]

        from ironforgedbot.commands.holiday.outcomes import gif

        await gif.result_gif(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        # Should send a GIF URL
        gif_url = self.interaction.followup.send.call_args[0][0]
        self.assertTrue(gif_url.startswith("http"))

    async def test_gif_history_tracking(self):
        """Test that GIF history prevents recent repeats."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()
            handler.GIFS = [f"http://test.com/gif{i}.gif" for i in range(10)]
            handler.gif_history = []

        from ironforgedbot.commands.holiday.outcomes import gif

        # Send multiple GIFs
        for _ in range(3):
            self.interaction.followup.send.reset_mock()
            await gif.result_gif(handler, self.interaction)
            sent_gif = self.interaction.followup.send.call_args[0][0]
            # Verify the sent GIF was added to history
            self.assertIn(sent_gif, handler.gif_history)

        # History should track recent GIFs
        self.assertEqual(len(handler.gif_history), 3)
