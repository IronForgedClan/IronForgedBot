import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.commands.trickortreat.outcomes import backrooms
from ironforgedbot.commands.trickortreat.outcomes.backrooms import (
    BackroomsView,
    DoorOutcome,
)
from ironforgedbot.commands.trickortreat.types import IngotAdjustment
from ironforgedcore.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    create_test_trick_or_treat_handler,
)


class TestBackroomsOutcome(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("TestUser", [ROLE.MEMBER])
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    async def test_result_backrooms_creates_room_one_view(self):
        handler = create_test_trick_or_treat_handler()

        await backrooms.result_backrooms(handler, self.interaction)

        self.interaction.followup.send.assert_called_once()
        call_kwargs = self.interaction.followup.send.call_args.kwargs
        view = call_kwargs["view"]
        self.assertIsInstance(view, BackroomsView)
        self.assertEqual(view.room_number, 1)
        self.assertEqual(view.pot, 0)
        self.assertEqual(len(view.children), 3)
        self.assertEqual(view.door_outcomes, [DoorOutcome.TREASURE] * 3)
        self.assertIs(view.last_interaction, self.interaction)
        self.assertIsNotNone(call_kwargs["embed"])
        self.assertIn("Room one is safe", call_kwargs["embed"].description)

    async def test_door_choice_adds_pot_and_offers_cashout_or_continue(self):
        handler = create_test_trick_or_treat_handler()
        view = BackroomsView(
            handler,
            self.test_user.id,
            [DoorOutcome.TREASURE] * 3,
            ["Door 1", "Door 2", "Door 3"],
            interaction=self.interaction,
        )
        view.message = AsyncMock()

        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.backrooms.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch(
            "ironforgedbot.commands.trickortreat.outcomes.backrooms.random.randint",
            return_value=1500,
        ):
            await view.children[0].callback(self.interaction)

        self.assertEqual(view.pot, 1500)
        self.assertEqual(view.phase, "decision")
        self.assertFalse(view.finished)
        self.assertEqual(len(view.children), 2)
        self.assertEqual(
            {button.custom_id for button in view.children},
            {"backrooms_cash_out", "backrooms_continue"},
        )
        self.interaction.response.defer.assert_awaited_once()

    async def test_continue_advances_room_and_rebuilds_door_buttons(self):
        handler = create_test_trick_or_treat_handler()
        view = BackroomsView(
            handler,
            self.test_user.id,
            [DoorOutcome.TREASURE] * 3,
            ["Door 1", "Door 2", "Door 3"],
            room_number=1,
            pot=2000,
        )
        view.phase = "decision"
        view.message = AsyncMock()

        with patch(
            "ironforgedbot.commands.trickortreat.outcomes.backrooms.random.choices",
            return_value=[DoorOutcome.BARGAIN] * 3,
        ), patch(
            "ironforgedbot.commands.trickortreat.outcomes.backrooms.random.sample",
            return_value=["Room 2 Door"] * 3,
        ):
            await view._continue_callback(self.interaction)

        self.assertEqual(view.room_number, 2)
        self.assertEqual(view.phase, "doors")
        self.assertEqual(len(view.children), 3)
        self.assertEqual(view.door_outcomes, [DoorOutcome.BARGAIN] * 3)
        self.assertEqual(view.pot, 2000)

    async def test_cash_out_credits_pot_once_and_finishes_run(self):
        handler = create_test_trick_or_treat_handler()
        handler._adjust_ingots = AsyncMock(return_value=IngotAdjustment(27_000, 25_000))
        handler._get_user_info = AsyncMock(return_value=("TestUser", 27_000))
        view = BackroomsView(
            handler,
            self.test_user.id,
            [DoorOutcome.TREASURE] * 3,
            ["Door 1", "Door 2", "Door 3"],
            room_number=2,
            pot=30_000,
        )
        view.phase = "decision"
        view.message = AsyncMock()

        await view._cash_out_callback(self.interaction)

        handler._adjust_ingots.assert_awaited_once_with(
            self.interaction,
            25_000,
            self.test_user,
            reason="Trick or treat: backrooms cash out",
        )
        self.assertTrue(view.finished)
        self.assertEqual(view.pot, 0)
        self.assertEqual(len(view.children), 0)
        view.message.edit.assert_awaited()

    async def test_timeout_banks_unbanked_pot(self):
        handler = create_test_trick_or_treat_handler()
        handler._adjust_ingots = AsyncMock(return_value=IngotAdjustment(6000, 4000))
        handler._get_user_info = AsyncMock(return_value=("TestUser", 6000))
        view = BackroomsView(
            handler,
            self.test_user.id,
            [DoorOutcome.TREASURE] * 3,
            ["Door 1", "Door 2", "Door 3"],
            pot=4000,
            interaction=self.interaction,
        )
        view.message = AsyncMock()

        await view.on_timeout()

        handler._adjust_ingots.assert_awaited_once()
        self.assertTrue(view.finished)
        self.assertEqual(view.pot, 0)

    async def test_five_room_limit_blocks_continue_button(self):
        handler = create_test_trick_or_treat_handler()
        view = BackroomsView(
            handler,
            self.test_user.id,
            [DoorOutcome.TREASURE] * 3,
            ["Door 1", "Door 2", "Door 3"],
            room_number=5,
            pot=1000,
        )
        view.phase = "decision"
        view._add_run_buttons()

        self.assertEqual(
            [button.custom_id for button in view.children], ["backrooms_cash_out"]
        )

    async def test_wrong_user_cannot_choose_door(self):
        handler = create_test_trick_or_treat_handler()
        view = BackroomsView(
            handler,
            self.test_user.id,
            [DoorOutcome.TREASURE] * 3,
            ["Door 1", "Door 2", "Door 3"],
        )
        other_user = create_test_member("OtherUser", [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=other_user)

        await view.children[0].callback(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "These aren't your backrooms!", ephemeral=True
        )
