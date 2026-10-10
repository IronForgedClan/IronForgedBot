import unittest
from unittest.mock import patch

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

    def test_room_one_guarantees_treasure(self):
        weights = get_room_outcome_weights(1, 0, self.weights)

        self.assertEqual(weights, {DoorOutcome.TREASURE: 1.0})

    def test_room_weights_come_from_supplied_config(self):
        weights = {"2": {"treasure": 1.0}}

        result = get_room_outcome_weights(2, 0, weights)

        self.assertEqual(result, {DoorOutcome.TREASURE: 1.0})

    def test_missing_room_weights_raise(self):
        with self.assertRaisesRegex(ValueError, "Invalid backrooms room number"):
            get_room_outcome_weights(6, 0, self.weights)

    def test_bargain_weights_require_room_two_and_nonzero_pot(self):
        room_two_without_pot = get_room_outcome_weights(2, 0, self.weights)
        room_two_with_pot = get_room_outcome_weights(2, 1, self.weights)

        self.assertNotIn(DoorOutcome.BARGAIN, room_two_without_pot)
        self.assertAlmostEqual(room_two_without_pot[DoorOutcome.TREASURE], 0.48)
        self.assertAlmostEqual(room_two_without_pot[DoorOutcome.ESCAPE], 0.26)
        self.assertEqual(room_two_with_pot[DoorOutcome.BARGAIN], 0.10)
        self.assertAlmostEqual(sum(room_two_without_pot.values()), 1.0)
        self.assertAlmostEqual(sum(room_two_with_pot.values()), 1.0)

    def test_monster_probability_rises_after_safe_first_room(self):
        monster_weights = [
            sum(
                get_room_outcome_weights(room, 1, self.weights).get(outcome, 0)
                for outcome in (
                    DoorOutcome.FATAL_MONSTER,
                    DoorOutcome.ESCAPABLE_MONSTER,
                )
            )
            for room in range(1, 6)
        ]

        for actual, expected in zip(monster_weights, [0.0, 0.26, 0.32, 0.39, 0.57]):
            self.assertAlmostEqual(actual, expected)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_treasure_adds_room_scaled_reward_to_pot(self, mock_randint):
        mock_randint.return_value = 2000

        result = await process_door_choice(
            self.handler, DoorOutcome.TREASURE, room_number=2, pot=0
        )

        self.assertEqual(result.pot, 2000)
        self.assertFalse(result.terminal)
        self.assertFalse(result.bank_pot)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_treasure_payout_cannot_exceed_cap(self, mock_randint):
        mock_randint.return_value = 6000

        result = await process_door_choice(
            self.handler, DoorOutcome.TREASURE, room_number=5, pot=24_000
        )

        self.assertEqual(result.pot, 25_000)
        self.assertTrue(result.terminal)
        self.assertTrue(result.bank_pot)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_maximum_treasure_path_stays_under_run_cap(self, mock_randint):
        mock_randint.side_effect = [2000, 3000, 4000, 5000, 6000]
        pot = 0

        for room_number in range(1, 6):
            result = await process_door_choice(
                self.handler, DoorOutcome.TREASURE, room_number, pot
            )
            pot = result.pot

        self.assertEqual(pot, 20_000)
        self.assertLessEqual(pot, 25_000)

    async def test_fatal_monster_ends_run_and_empties_pot(self):
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Fatal encounter"
        ):
            result = await process_door_choice(
                self.handler, DoorOutcome.FATAL_MONSTER, room_number=3, pot=10_000
            )

        self.assertEqual(result.pot, 0)
        self.assertTrue(result.terminal)
        self.assertFalse(result.bank_pot)

    async def test_escapable_monster_halves_pot_and_continues(self):
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Escaped encounter"
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.ESCAPABLE_MONSTER,
                room_number=2,
                pot=10_001,
            )

        self.assertEqual(result.pot, 5_001)
        self.assertFalse(result.terminal)
        self.assertFalse(result.bank_pot)

    @patch("ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint")
    async def test_bargain_costs_quarter_pot_and_adds_room_reward(self, mock_randint):
        mock_randint.return_value = 2000

        with patch.object(
            self.handler,
            "_get_backrooms_message",
            return_value="A stranger offers a deal.",
        ):
            result = await process_door_choice(
                self.handler, DoorOutcome.BARGAIN, room_number=2, pot=10_000
            )

        self.assertEqual(result.pot, 9_500)
        self.assertEqual(result.impact, ("Bargain", "−🪙2,500 / +🪙2,000"))
        self.assertFalse(result.terminal)

    async def test_safe_escape_ends_and_banks_pot(self):
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Safe exit"
        ):
            result = await process_door_choice(
                self.handler, DoorOutcome.ESCAPE, room_number=2, pot=5000
            )

        self.assertEqual(result.pot, 5000)
        self.assertTrue(result.terminal)
        self.assertTrue(result.bank_pot)

    async def test_escapable_monster_on_final_room_banks_reduced_pot(self):
        with patch.object(
            self.handler, "_get_backrooms_message", return_value="Escaped encounter"
        ):
            result = await process_door_choice(
                self.handler,
                DoorOutcome.ESCAPABLE_MONSTER,
                room_number=5,
                pot=10_000,
            )

        self.assertEqual(result.pot, 5000)
        self.assertTrue(result.terminal)
        self.assertTrue(result.bank_pot)
