import asyncio
import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    BACKROOMS_BARGAIN_POT_LOSS_PERCENT,
    BACKROOMS_BARGAIN_START_ROOM,
    BACKROOMS_DOOR_COUNT,
    BACKROOMS_ESCAPABLE_MONSTER_POT_LOSS_PERCENT,
    BACKROOMS_MAX_PAYOUT,
    BACKROOMS_MAX_ROOMS,
    BACKROOMS_TREASURE_RANGES,
)
from ironforgedbot.common.responses import build_response_embed

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


class DoorOutcome(Enum):
    """Possible outcomes behind each door."""

    TREASURE = "treasure"
    FATAL_MONSTER = "fatal_monster"
    ESCAPABLE_MONSTER = "escapable_monster"
    ESCAPE = "escape"
    BARGAIN = "bargain"


ROOM_OUTCOME_WEIGHTS = {
    1: {
        DoorOutcome.TREASURE: 1.0,
    },
    2: {
        DoorOutcome.TREASURE: 0.20,
        DoorOutcome.FATAL_MONSTER: 0.17,
        DoorOutcome.ESCAPABLE_MONSTER: 0.28,
        DoorOutcome.ESCAPE: 0.20,
        DoorOutcome.BARGAIN: 0.15,
    },
    3: {
        DoorOutcome.TREASURE: 0.175,
        DoorOutcome.FATAL_MONSTER: 0.20,
        DoorOutcome.ESCAPABLE_MONSTER: 0.30,
        DoorOutcome.ESCAPE: 0.175,
        DoorOutcome.BARGAIN: 0.15,
    },
    4: {
        DoorOutcome.TREASURE: 0.15,
        DoorOutcome.FATAL_MONSTER: 0.22,
        DoorOutcome.ESCAPABLE_MONSTER: 0.33,
        DoorOutcome.ESCAPE: 0.15,
        DoorOutcome.BARGAIN: 0.15,
    },
    5: {
        DoorOutcome.TREASURE: 0.125,
        DoorOutcome.FATAL_MONSTER: 0.24,
        DoorOutcome.ESCAPABLE_MONSTER: 0.36,
        DoorOutcome.ESCAPE: 0.125,
        DoorOutcome.BARGAIN: 0.15,
    },
}


@dataclass(frozen=True)
class DoorResolution:
    message: str
    pot: int
    terminal: bool
    bank_pot: bool
    impact: tuple[str, str] | None = None


def get_room_outcome_weights(room_number: int, pot: int) -> dict[DoorOutcome, float]:
    """Return room outcome weights, omitting bargains when no pot is at risk."""
    if room_number not in ROOM_OUTCOME_WEIGHTS:
        raise ValueError(f"Invalid backrooms room number: {room_number}")

    weights = ROOM_OUTCOME_WEIGHTS[room_number].copy()
    if DoorOutcome.BARGAIN in weights and pot <= 0:
        bargain_weight = weights.pop(DoorOutcome.BARGAIN)
        weights[DoorOutcome.TREASURE] += bargain_weight / 2
        weights[DoorOutcome.ESCAPE] += bargain_weight / 2

    return weights


def _format_ingots(handler: "TrickOrTreatHandler", amount: int) -> str:
    return f"{handler.ingot_icon}{amount:,}"


def _calculate_pot_loss(pot: int, percent: int) -> int:
    return min(pot, pot * percent // 100)


async def process_door_choice(
    handler: "TrickOrTreatHandler",
    outcome: DoorOutcome,
    room_number: int,
    pot: int,
) -> DoorResolution:
    """Resolve selected door without crediting or debiting the player's balance."""
    if not 1 <= room_number <= BACKROOMS_MAX_ROOMS:
        raise ValueError(f"Invalid backrooms room number: {room_number}")

    terminal_room = room_number == BACKROOMS_MAX_ROOMS

    match outcome:
        case DoorOutcome.TREASURE:
            minimum, maximum = BACKROOMS_TREASURE_RANGES[room_number - 1]
            amount = random.randint(minimum, maximum)
            added_amount = min(amount, BACKROOMS_MAX_PAYOUT - pot)
            new_pot = min(BACKROOMS_MAX_PAYOUT, pot + amount)
            message = random.choice(handler.backrooms["treasure_messages"])
            impact = ("Found", f"+{_format_ingots(handler, added_amount)}")
            return DoorResolution(
                message, new_pot, terminal_room, terminal_room, impact
            )

        case DoorOutcome.FATAL_MONSTER:
            message = random.choice(handler.backrooms["fatal_monster_messages"])
            impact = ("Lost", _format_ingots(handler, pot))
            return DoorResolution(message, 0, True, False, impact)

        case DoorOutcome.ESCAPABLE_MONSTER:
            lost_amount = _calculate_pot_loss(
                pot, BACKROOMS_ESCAPABLE_MONSTER_POT_LOSS_PERCENT
            )
            remaining_pot = pot - lost_amount
            message = random.choice(handler.backrooms["monster_messages"])
            impact = ("Lost", _format_ingots(handler, lost_amount))
            return DoorResolution(
                message, remaining_pot, terminal_room, terminal_room, impact
            )

        case DoorOutcome.ESCAPE:
            message = random.choice(handler.backrooms["escape_messages"])
            return DoorResolution(message, pot, True, True)

        case DoorOutcome.BARGAIN:
            if room_number < BACKROOMS_BARGAIN_START_ROOM or pot <= 0:
                raise ValueError(
                    "Backrooms bargain requires room two and a positive pot"
                )

            minimum, maximum = BACKROOMS_TREASURE_RANGES[room_number - 1]
            bonus = random.randint(minimum, maximum)
            lost_amount = _calculate_pot_loss(pot, BACKROOMS_BARGAIN_POT_LOSS_PERCENT)
            new_pot = min(BACKROOMS_MAX_PAYOUT, pot - lost_amount + bonus)
            message = handler.backrooms["bargain_message"]
            impact = (
                "Bargain",
                f"−{_format_ingots(handler, lost_amount)} / "
                f"+{_format_ingots(handler, bonus)}",
            )
            return DoorResolution(
                message, new_pot, terminal_room, terminal_room, impact
            )

    raise ValueError(f"Unsupported backrooms outcome: {outcome}")


class BackroomsView(discord.ui.View):
    """In-memory push-your-luck run with a five-room maximum."""

    def __init__(
        self,
        handler: "TrickOrTreatHandler",
        user_id: int,
        door_outcomes: list[DoorOutcome],
        door_labels: list[str],
        room_number: int = 1,
        pot: int = 0,
        interaction: discord.Interaction | None = None,
        thumbnail_url: str | None = None,
    ):
        super().__init__(timeout=45.0)
        self.handler = handler
        self.user_id = user_id
        self.door_outcomes = door_outcomes
        self.door_labels = door_labels
        self.room_number = room_number
        self.pot = pot
        self.thumbnail_url = thumbnail_url or handler._get_random_from_list(
            handler.backrooms["thumbnails"], handler.history["backrooms_thumbnail"]
        )
        self.has_interacted = False
        self.processing = False
        self.settling = False
        self.finished = False
        self.phase = "doors"
        self.message: Optional[discord.Message] = None
        self.last_interaction = interaction
        self._add_door_buttons()

    def _cleanup(self) -> None:
        self.handler = None
        self.door_outcomes = None
        self.door_labels = None
        self.last_interaction = None

    def _add_door_buttons(self) -> None:
        self.clear_items()
        for index in range(BACKROOMS_DOOR_COUNT):
            button = discord.ui.Button(
                label=self.door_labels[index],
                style=discord.ButtonStyle.secondary,
                custom_id=f"backrooms_door_{index}",
                row=0,
            )
            button.callback = self._create_door_callback(index)
            self.add_item(button)

    def _add_run_buttons(self, retry_only: bool = False) -> None:
        self.clear_items()
        cash_out_button = discord.ui.Button(
            label="💰 Retry cash out" if retry_only else "💰 Cash out",
            style=discord.ButtonStyle.success,
            custom_id="backrooms_cash_out",
            row=0,
        )
        cash_out_button.callback = self._cash_out_callback
        self.add_item(cash_out_button)

        if not retry_only and self.room_number < BACKROOMS_MAX_ROOMS:
            continue_button = discord.ui.Button(
                label="➡️ Continue deeper",
                style=discord.ButtonStyle.primary,
                custom_id="backrooms_continue",
                row=0,
            )
            continue_button.callback = self._continue_callback
            self.add_item(continue_button)

    async def _edit_message(
        self,
        content: str,
        fields: list[tuple[str, str]] | None = None,
        footer: str | None = None,
    ) -> None:
        embed = self._build_embed(content, fields, footer=footer)
        if self.message:
            await self.message.edit(embed=embed, view=self)

    def _build_embed(
        self,
        description: str,
        fields: list[tuple[str, str]] | None = None,
        color: discord.Color | None = None,
        thumbnail_url: str | None = None,
        footer: str | None = None,
    ) -> discord.Embed:
        embed = build_response_embed(
            "Backrooms", description, color or discord.Color.orange()
        )
        embed.set_thumbnail(url=thumbnail_url or self.thumbnail_url)
        for name, value in fields or []:
            embed.add_field(name=name, value=value, inline=True)
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def _cash_out(
        self,
        interaction: discord.Interaction,
        message: str,
        impact: tuple[str, str] | None = None,
    ) -> bool:
        if self.finished or self.settling:
            return self.finished

        self.pot = min(max(self.pot, 0), BACKROOMS_MAX_PAYOUT)
        self.settling = True
        if self.pot > 0:
            assert interaction.guild
            user_nickname, _ = await self.handler._get_user_info(self.user_id)
            adjustment = await self.handler._adjust_ingots(
                interaction,
                self.pot,
                interaction.guild.get_member(self.user_id),
                reason="Trick or treat: backrooms cash out",
            )
            if adjustment.failure is not None:
                self.settling = False
                self.phase = "cash_out"
                self._add_run_buttons(retry_only=True)
                fields = [impact] if impact else []
                fields.append(
                    ("Still unbanked", _format_ingots(self.handler, self.pot))
                )
                await self._edit_message(
                    f"{message}\n\nCash-out failed. Select the retry button to try again.",
                    fields,
                )
                return False

            assert adjustment.new_total is not None
            balance = adjustment.new_total
        else:
            user_nickname, balance = await self.handler._get_user_info(self.user_id)

        banked_amount = self.pot
        self.finished = True
        self.settling = False
        self.pot = 0
        self.clear_items()
        fields = [impact] if impact else []
        fields.extend(
            [
                ("Banked", _format_ingots(self.handler, banked_amount)),
                (
                    "Balance",
                    f"{user_nickname} has {_format_ingots(self.handler, balance)}",
                ),
            ]
        )
        await self._edit_message(message, fields)
        self.stop()
        self._cleanup()
        return True

    async def _end_without_cash_out(
        self,
        interaction: discord.Interaction,
        message: str,
        impact: tuple[str, str] | None = None,
    ) -> None:
        user_nickname, total = await self.handler._get_user_info(self.user_id)
        self.finished = True
        self.clear_items()
        fields = [impact] if impact else []
        fields.append(
            ("Balance", f"{user_nickname} has {_format_ingots(self.handler, total)}")
        )
        await self._edit_message(message, fields)
        self.stop()
        self._cleanup()

    def _create_door_callback(self, door_index: int):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "These aren't your backrooms!", ephemeral=True
                )
                return

            if self.has_interacted or self.finished:
                await interaction.response.send_message(
                    "You already chose a corridor!", ephemeral=True
                )
                return

            self.has_interacted = True
            self.processing = True
            self.last_interaction = interaction
            await interaction.response.defer()

            door_label = self.door_labels[door_index]
            suspense_message = self.handler.backrooms["opening_door"].format(
                door=door_label
            )
            suspense_embed = self._build_embed(
                suspense_message,
                color=discord.Color.darker_grey(),
                thumbnail_url=self.handler.backrooms["suspense_thumbnail"],
            )
            if self.message:
                await self.message.edit(embed=suspense_embed, view=None)

            await asyncio.sleep(8)
            outcome = self.door_outcomes[door_index]
            resolution = await process_door_choice(
                self.handler, outcome, self.room_number, self.pot
            )
            self.pot = resolution.pot
            self.processing = False

            if resolution.terminal:
                if resolution.bank_pot:
                    await self._cash_out(
                        interaction, resolution.message, resolution.impact
                    )
                else:
                    await self._end_without_cash_out(
                        interaction, resolution.message, resolution.impact
                    )
                return

            self.phase = "decision"
            self.has_interacted = False
            self._add_run_buttons()
            fields = [resolution.impact] if resolution.impact else []
            fields.append(("Unbanked haul", _format_ingots(self.handler, self.pot)))
            expires_timestamp = f"<t:{int(interaction.created_at.timestamp()) + 45}:R>"
            await self._edit_message(
                f"{resolution.message}\n\nCash out or continue deeper.",
                fields,
                footer=f"Decide {expires_timestamp}.",
            )

        return callback

    async def _cash_out_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "These aren't your backrooms!", ephemeral=True
            )
            return

        if (
            self.has_interacted
            or self.finished
            or self.phase not in {"decision", "cash_out"}
        ):
            await interaction.response.send_message(
                "You already chose!", ephemeral=True
            )
            return

        self.has_interacted = True
        self.last_interaction = interaction
        await interaction.response.defer()
        await self._cash_out(interaction, "You leave the backrooms with your haul.")
        if not self.finished:
            self.has_interacted = False

    async def _continue_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "These aren't your backrooms!", ephemeral=True
            )
            return

        if self.has_interacted or self.finished or self.phase != "decision":
            await interaction.response.send_message(
                "You already chose!", ephemeral=True
            )
            return

        self.has_interacted = True
        self.last_interaction = interaction
        await interaction.response.defer()
        self.room_number += 1
        weights = get_room_outcome_weights(self.room_number, self.pot)
        self.door_outcomes = random.choices(
            list(weights), weights=list(weights.values()), k=BACKROOMS_DOOR_COUNT
        )
        self.door_labels = random.sample(
            self.handler.backrooms["door_labels"], BACKROOMS_DOOR_COUNT
        )
        expires_timestamp = f"<t:{int(interaction.created_at.timestamp()) + 45}:R>"
        intro_message = self.handler.backrooms["continue_intro"]
        self.phase = "doors"
        self.has_interacted = False
        self._add_door_buttons()
        await self._edit_message(
            intro_message,
            [("Unbanked haul", _format_ingots(self.handler, self.pot))],
            footer=f"Decide {expires_timestamp}.",
        )

    async def on_timeout(self) -> None:
        if self.finished or self.processing or self.settling:
            return

        interaction = self.last_interaction
        if interaction is None:
            self.clear_items()
            self._cleanup()
            return

        await self._cash_out(
            interaction,
            self.handler.backrooms["expired"],
        )


async def result_backrooms(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Start a five-room push-your-luck Backrooms run."""
    assert interaction.guild

    room_number = 1
    pot = 0
    weights = get_room_outcome_weights(room_number, pot)
    outcomes = random.choices(
        list(weights), weights=list(weights.values()), k=BACKROOMS_DOOR_COUNT
    )
    selected_labels = random.sample(
        handler.backrooms["door_labels"], BACKROOMS_DOOR_COUNT
    )

    expires_timestamp = f"<t:{int(interaction.created_at.timestamp()) + 45}:R>"
    view = BackroomsView(
        handler,
        interaction.user.id,
        outcomes,
        selected_labels,
        room_number=room_number,
        pot=pot,
        interaction=interaction,
    )
    embed = view._build_embed(
        handler.backrooms["intro"],
        [("Unbanked haul", _format_ingots(handler, pot))],
        footer=f"Decide {expires_timestamp}.",
    )
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message
