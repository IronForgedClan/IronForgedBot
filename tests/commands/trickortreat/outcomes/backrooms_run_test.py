import unittest
from unittest.mock import patch

from ironforgedbot.commands.trickortreat.outcomes import backrooms
from ironforgedbot.commands.trickortreat.outcomes.backrooms import (
    DoorOutcome,
    get_room_outcome_weights,
    process_door_choice,
)
from tests.helpers import create_test_trick_or_treat_handler


class TestBackroomsRun(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.handler = create_test_trick_or_treat_handler()
        self.weights = self.handler.backrooms["room_outcome_weights"]
        self.treasure_ranges = [(11, 19), (23, 37), (41, 59), (61, 83)]
        self.max_payout = 733
        self.bargain_start_room = 3
        self.bargain_loss_percent = 37
        self.escapable_loss_percent = 43
        self._config_patch = patch.multiple(
            backrooms,
            BACKROOMS_TREASURE_RANGES=self.treasure_ranges,
            BACKROOMS_MAX_PAYOUT=self.max_payout,
            BACKROOMS_MAX_ROOMS=len(self.treasure_ranges),
            BACKROOMS_BARGAIN_START_ROOM=self.bargain_start_room,
            BACKROOMS_BARGAIN_POT_LOSS_PERCENT=self.bargain_loss_percent,
            BACKROOMS_ESCAPABLE_MONSTER_POT_LOSS_PERCENT=self.escapable_loss_percent,
        )
        self._config_patch.start()
        self.addCleanup(self._config_patch.stop)

    def test_room_one_guarantees_treasure(self):
        weights = get_room_outcome_weights(1, 0, self.weights)

        self.assertEqual(weights, {DoorOutcome.TREASURE: 1.0})

    def test_room_weights_come_from_supplied_config(self):
        weights = {"2": {"treasure": 1.0}}

        result = get_room_outcome_weights(2, 0, weights)

        self.assertEqual(result, {DoorOutcome.TREASURE: 1.0})

    def test_missing_room_weights_raise(self):
        with self.assertRaisesRegex(ValueError, "Invalid backrooms room number"):
            get_room_outcome_weights(2, 0, {"1": {"treasure": 1.0}})

    def test_bargain_weights_split_when_pot_is_zero(self):
        start_room = self.bargain_start_room
        room_without_pot = get_room_outcome_weights(start_room, 0, self.weights)
        room_with_pot = get_room_outcome_weights(start_room, 1, self.weights)
        room_config = self.weights[str(start_room)]

        self.assertNotIn(DoorOutcome.BARGAIN, room_without_pot)
        self.assertAlmostEqual(
            room_without_pot[DoorOutcome.TREASURE],
            room_config["treasure"] + room_config["bargain"] / 2,
        )
        self.assertAlmostEqual(
            room_without_pot[DoorOutcome.ESCAPE],
            room_config["escape"] + room_config["bargain"] / 2,
        )
        self.assertEqual(room_with_pot[DoorOutcome.BARGAIN], room_config["bargain"])
        self.assertAlmostEqual(sum(room_without_pot.values()), 1.0)
        self.assertAlmostEqual(sum(room_with_pot.values()), 1.0)

    def test_monster_probability_rises_after_safe_first_room(self):
        monster_weights = [
            sum(
                get_room_outcome_weights(room, 1, self.weights).get(outcome, 0)
                for outcome in (
                    DoorOutcome.FATAL_MONSTER,
                    DoorOutcome.ESCAPABLE_MONSTER,
                )
            )
            for room in range(1, len(self.treasure_ranges) + 1)
        ]

        self.assertEqual(monster_weights[0], 0)
        self.assertEqual(monster_weights, sorted(monster_weights))
        for room_number, actual in enumerate(monster_weights, start=1):
            configured = self.weights[str(room_number)]
            expected = configured.get("fatal_monster", 0) + configured.get(
                "escapable_monster", 0
            )
            self.assertAlmostEqual(actual, expected)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_treasure_adds_room_scaled_reward_to_pot(self, mock_randint):
        mock_randint.return_value = 29

        result = await process_door_choice(
            self.handler, DoorOutcome.TREASURE, room_number=2, pot=0
        )

        self.assertEqual(result.pot, 29)
        self.assertFalse(result.terminal)
        self.assertFalse(result.bank_pot)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_treasure_payout_cannot_exceed_cap(self, mock_randint):
        mock_randint.return_value = max(self.treasure_ranges[-1])

        result = await process_door_choice(
            self.handler,
            DoorOutcome.TREASURE,
            room_number=len(self.treasure_ranges),
            pot=self.max_payout - 13,
        )

        self.assertEqual(result.pot, self.max_payout)
        self.assertTrue(result.terminal)
        self.assertTrue(result.bank_pot)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_maximum_treasure_path_stays_under_run_cap(self, mock_randint):
        mock_randint.side_effect = [maximum for _, maximum in self.treasure_ranges]
        pot = 0

        for room_number in range(1, len(self.treasure_ranges) + 1):
            result = await process_door_choice(
                self.handler, DoorOutcome.TREASURE, room_number, pot
            )
            pot = result.pot

        self.assertEqual(pot, sum(maximum for _, maximum in self.treasure_ranges))
        self.assertLessEqual(pot, self.max_payout)

    async def test_fatal_monster_ends_run_and_empties_pot(self):
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Fatal encounter"
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.FATAL_MONSTER,
                room_number=self.bargain_start_room,
                pot=1001,
            )

        self.assertEqual(result.pot, 0)
        self.assertTrue(result.terminal)
        self.assertFalse(result.bank_pot)

    async def test_escapable_monster_applies_configured_loss_and_continues(self):
        starting_pot = 1001
        expected_loss = starting_pot * self.escapable_loss_percent // 100
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Escaped encounter"
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.ESCAPABLE_MONSTER,
                room_number=self.bargain_start_room - 1,
                pot=starting_pot,
            )

        self.assertEqual(result.pot, starting_pot - expected_loss)
        self.assertFalse(result.terminal)
        self.assertFalse(result.bank_pot)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_bargain_applies_configured_loss_and_room_reward(self, mock_randint):
        starting_pot = 1001
        bonus = 47
        lost_amount = starting_pot * self.bargain_loss_percent // 100
        mock_randint.return_value = bonus

        with patch.object(
            self.handler,
            "_get_backrooms_message",
            return_value="A stranger offers a deal.",
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.BARGAIN,
                room_number=self.bargain_start_room,
                pot=starting_pot,
            )

        self.assertEqual(result.pot, starting_pot - lost_amount + bonus)
        self.assertEqual(
            result.impact,
            ("Bargain", f"−🪙{lost_amount:,} / +🪙{bonus:,}"),
        )
        self.assertFalse(result.terminal)

    async def test_safe_escape_ends_and_banks_pot(self):
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Safe exit"
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.ESCAPE,
                room_number=self.bargain_start_room,
                pot=321,
            )

        self.assertEqual(result.pot, 321)
        self.assertTrue(result.terminal)
        self.assertTrue(result.bank_pot)

    async def test_escapable_monster_on_final_room_banks_reduced_pot(self):
        starting_pot = 1001
        expected_loss = starting_pot * self.escapable_loss_percent // 100
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Escaped encounter"
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.ESCAPABLE_MONSTER,
                room_number=len(self.treasure_ranges),
                pot=starting_pot,
            )

        self.assertEqual(result.pot, starting_pot - expected_loss)
        self.assertTrue(result.terminal)
        self.assertTrue(result.bank_pot)
