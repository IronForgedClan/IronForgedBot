"""Jackpot outcome for trick-or-treat."""

from typing import TYPE_CHECKING

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import JACKPOT_VALUE
from ironforgedbot.state import STATE

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


async def result_jackpot(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Award the jackpot prize (1 million ingots) to the player.

    Only one player can claim the jackpot per event. Subsequent attempts
    receive a consolation message.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild
    if STATE.state["trick_or_treat_jackpot_claimed"]:
        embed = handler._build_embed(handler.JACKPOT_CLAIMED_MESSAGE)
        return await interaction.followup.send(embed=embed)

    user_new_total = await handler._adjust_ingots(
        interaction,
        JACKPOT_VALUE,
        interaction.guild.get_member(interaction.user.id),
        reason="Trick or treat: jackpot",
    )

    STATE.state["trick_or_treat_jackpot_claimed"] = True

    # Get member nickname from database
    user_nickname, _ = await handler._get_user_info(interaction.user.id)

    message = handler.JACKPOT_SUCCESS_PREFIX.format(
        mention=interaction.user.mention,
        ingot_icon=handler.ingot_icon,
        amount=JACKPOT_VALUE,
    )
    embed = handler._build_embed(
        message + handler._get_balance_message(user_nickname, user_new_total or 0)
    )
    embed.set_thumbnail(
        url=(
            "https://oldschool.runescape.wiki/images/thumb/"
            "Great_cauldron_%28overflowing%29.png"
            "/1280px-Great_cauldron_%28overflowing%29.png"
        )
    )
    return await interaction.followup.send(embed=embed)
