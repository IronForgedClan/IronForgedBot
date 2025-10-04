import asyncio
import json
import unittest
from typing import Counter
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import discord

from ironforgedbot.commands.holiday.trick_or_treat_handler import (
    HIGH_INGOT_MAX,
    HIGH_INGOT_MIN,
    LOW_INGOT_MAX,
    LOW_INGOT_MIN,
    TrickOrTreat,
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
        "OFFER": "Double or nothing {ingot_icon}{amount:,}",
        "WIN": "You won {ingot_icon}{amount:,}",
        "LOSE": "You lost {ingot_icon}{amount:,}",
        "EXPIRED": "Expired {ingot_icon}{amount:,}"
    },
    "STEAL": {
        "OFFER": "Steal {ingot_icon}{amount:,} penalty {ingot_icon}{penalty:,}",
        "SUCCESS": "Success {ingot_icon}{amount:,} from {target_mention}",
        "FAILURE": "Failed {target_mention} penalty {ingot_icon}{penalty:,}",
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
            self.test_user.id, 500, None, "Trick or treat win"
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
            self.test_user.id, -100, None, "Trick or treat loss"
        )
        self.assertEqual(result, 0)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    async def test_handle_ingot_result_positive(
        self, mock_ingot_service_class, mock_db
    ):
        """Test _handle_ingot_result with a positive outcome."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        # Mock _adjust_ingots to return a successful balance
        handler._adjust_ingots = AsyncMock(return_value=1500)

        await handler._handle_ingot_result(self.interaction, 500, is_positive=True)

        self.interaction.followup.send.assert_called_once()
        call_args = self.interaction.followup.send.call_args
        embed = call_args.kwargs["embed"]
        self.assertIsNotNone(embed)

    async def test_handle_ingot_result_no_ingots(self):
        """Test _handle_ingot_result when player has no ingots."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

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

        await handler.result_add_low(self.interaction)

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

        await handler.result_remove_high(self.interaction)

        handler._handle_ingot_result.assert_called_once()
        quantity = handler._handle_ingot_result.call_args[0][1]
        is_positive = handler._handle_ingot_result.call_args[1]["is_positive"]

        self.assertLessEqual(quantity, -HIGH_INGOT_MIN)
        self.assertGreater(quantity, -HIGH_INGOT_MAX)
        self.assertFalse(is_positive)

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.STATE")
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

        await handler.result_jackpot(self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("already claimed", embed.description.lower())

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.STATE")
    async def test_result_jackpot_success(self, mock_state):
        """Test successful jackpot claim."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data=MOCK_TRICK_OR_TREAT_DATA
            ),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"trick_or_treat_jackpot_claimed": False}
        handler._adjust_ingots = AsyncMock(return_value=1_500_000)

        await handler.result_jackpot(self.interaction)

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

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.STATE")
    async def test_result_double_or_nothing_creates_offer(
        self, mock_state, mock_ingot_service_class, mock_db
    ):
        """Test that double-or-nothing creates an offer with a button."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_state.state = {"double_or_nothing_offers": {}}
        mock_db_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_db_session

        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 2000
        mock_ingot_service.try_add_ingots = AsyncMock(return_value=mock_result)

        await handler.result_double_or_nothing(self.interaction)

        # Verify ingots were added
        mock_ingot_service.try_add_ingots.assert_called_once()

        # Verify a view was sent (has the button)
        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        self.assertIsNotNone(call_kwargs["view"])

        # Verify offer was stored in state
        user_id_str = str(self.test_user.id)
        self.assertIn(user_id_str, mock_state.state["double_or_nothing_offers"])

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    async def test_process_double_or_nothing_win(
        self, mock_ingot_service_class, mock_db
    ):
        """Test processing a winning double-or-nothing gamble."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        mock_db_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_db_session

        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 3000
        mock_ingot_service.try_add_ingots = AsyncMock(return_value=mock_result)

        # Mock random to always win
        with patch("ironforgedbot.commands.holiday.trick_or_treat_handler.random.random", return_value=0.3):
            await handler._process_double_or_nothing(self.interaction, 500)

        # Should add the amount (winning)
        mock_ingot_service.try_add_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_process_double_or_nothing_lose(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test processing a losing double-or-nothing gamble."""
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
            ingots=1000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 500
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)

        # Mock random to always lose
        with patch("ironforgedbot.commands.holiday.trick_or_treat_handler.random.random", return_value=0.7):
            await handler._process_double_or_nothing(self.interaction, 500)

        # Should remove the amount (losing)
        mock_ingot_service.try_remove_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_result_steal_creates_view_with_buttons(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test that steal creates an offer with target buttons and walk away."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # Create mock Leadership members
        leadership_member = create_test_member("LeadershipUser", [ROLE.LEADERSHIP])
        self.interaction.guild.members = [self.test_user, leadership_member]

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        await handler.result_steal(self.interaction)

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
        """Test steal when no Leadership members available."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        # No Leadership members
        self.interaction.guild.members = [self.test_user]

        await handler.result_steal(self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no targets", embed.description.lower())

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_result_steal_user_insufficient_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test steal when user doesn't have enough ingots for penalty."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        leadership_member = create_test_member("LeadershipUser", [ROLE.LEADERSHIP])
        self.interaction.guild.members = [self.test_user, leadership_member]

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        # User has very few ingots
        test_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=10,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=test_member
        )

        await handler.result_steal(self.interaction)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("need", embed.description.lower())

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_process_steal_success(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test successful steal (35% chance)."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        target_member = create_test_member("TargetUser", [ROLE.LEADERSHIP])

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=target_member.id,
            rank=RANK.IRON,
            ingots=5000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=target_db_member
        )

        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 3000
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)
        mock_ingot_service.try_add_ingots = AsyncMock(return_value=mock_result)

        # Mock random to always succeed
        with patch(
            "ironforgedbot.commands.holiday.trick_or_treat_handler.random.random",
            return_value=0.2,
        ):
            await handler._process_steal(self.interaction, 1000, target_member)

        # Should remove from target and add to user
        mock_ingot_service.try_remove_ingots.assert_called_once()
        mock_ingot_service.try_add_ingots.assert_called_once()
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.IngotService")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_process_steal_failure(
        self, mock_member_service_class, mock_ingot_service_class, mock_db
    ):
        """Test failed steal (65% chance, user loses penalty)."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        target_member = create_test_member("TargetUser", [ROLE.LEADERSHIP])

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        # User member with enough ingots
        user_db_member = create_test_db_member(
            nickname="TestUser",
            discord_id=self.test_user.id,
            rank=RANK.IRON,
            ingots=1000,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=user_db_member
        )

        mock_ingot_service = AsyncMock()
        mock_ingot_service_class.return_value = mock_ingot_service

        mock_result = MagicMock()
        mock_result.status = True
        mock_result.new_total = 500
        mock_ingot_service.try_remove_ingots = AsyncMock(return_value=mock_result)

        # Mock random to always fail
        with patch(
            "ironforgedbot.commands.holiday.trick_or_treat_handler.random.random",
            return_value=0.7,
        ):
            await handler._process_steal(self.interaction, 1000, target_member)

        # Should only remove penalty from user (half the amount)
        mock_ingot_service.try_remove_ingots.assert_called_once()
        call_args = mock_ingot_service.try_remove_ingots.call_args[0]
        self.assertEqual(call_args[1], -500)  # Half of 1000
        self.interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.db")
    @patch("ironforgedbot.commands.holiday.trick_or_treat_handler.MemberService")
    async def test_process_steal_target_has_zero_ingots(
        self, mock_member_service_class, mock_db
    ):
        """Test steal when target has no ingots."""
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=MOCK_TRICK_OR_TREAT_DATA),
        ):
            handler = TrickOrTreatHandler()

        target_member = create_test_member("TargetUser", [ROLE.LEADERSHIP])

        mock_db_session, mock_member_service = setup_database_service_mocks(
            mock_db, mock_member_service_class
        )

        target_db_member = create_test_db_member(
            nickname="TargetUser",
            discord_id=target_member.id,
            rank=RANK.IRON,
            ingots=0,
        )
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=target_db_member
        )

        # Mock random to succeed
        with patch(
            "ironforgedbot.commands.holiday.trick_or_treat_handler.random.random",
            return_value=0.2,
        ):
            await handler._process_steal(self.interaction, 1000, target_member)

        self.interaction.followup.send.assert_called_once()
        embed = self.interaction.followup.send.call_args.kwargs["embed"]
        self.assertIn("no ingots", embed.description.lower())
