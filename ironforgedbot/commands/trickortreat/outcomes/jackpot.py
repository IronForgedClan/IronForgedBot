import asyncio
from typing import TYPE_CHECKING

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import JACKPOT_VALUE
from ironforgedbot.commands.trickortreat.types import IngotAdjustmentFailure
from ironforgedbot.state import STATE

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )

_jackpot_claim_lock = asyncio.Lock()


async def result_jackpot(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Award the jackpot prize to the player.

    Only one player can claim the jackpot per event. Subsequent attempts
    receive a consolation message.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild
    async with _jackpot_claim_lock:
        if STATE.state["trick_or_treat_jackpot_claimed"]:
            message = handler._get_content_message(
                "jackpot.claimed_message", handler.jackpot["claimed_message"]
            )
            embed = handler._build_embed(message)
            return await interaction.followup.send(embed=embed)

        adjustment = await handler._adjust_ingots(
            interaction,
            JACKPOT_VALUE,
            interaction.guild.get_member(interaction.user.id),
            reason="Trick or treat: jackpot",
        )

        if adjustment.failure is not None:
            return

        assert adjustment.new_total is not None
        STATE.state["trick_or_treat_jackpot_claimed"] = True

        user_nickname, _ = await handler._get_user_info(interaction.user.id)

        message = handler._get_content_message(
            "jackpot.success_prefix", handler.jackpot["success_prefix"]
        ).format(
            mention=interaction.user.mention,
            ingot_icon=handler.ingot_icon,
            amount=JACKPOT_VALUE,
        )
        embed = handler._build_embed(
            message + handler._get_balance_message(user_nickname, adjustment.new_total)
        )
        embed.set_thumbnail(
            url=(
                "https://oldschool.runescape.wiki/images/thumb/"
                "Great_cauldron_%28overflowing%29.png"
                "/1280px-Great_cauldron_%28overflowing%29.png"
            )
        )
        return await interaction.followup.send(embed=embed)
