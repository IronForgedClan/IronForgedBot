from typing import TYPE_CHECKING

import discord

from ironforgedbot.common.responses import send_error_response
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import MemberService

if TYPE_CHECKING:
    from ironforgedbot.commands.trickortreat.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


async def result_remove_all_ingots_trick(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Pretend to remove all ingots from the player.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild
    async with db.get_session() as session:
        member_service = MemberService(session)
        member = await member_service.get_member_by_discord_id(interaction.user.id)

        if member is None:
            return await send_error_response(
                interaction,
                f"Member '{interaction.user.display_name}' not found in storage.",
            )

        if member.ingots < 1:
            embed = handler._build_no_ingots_error_response(member.nickname)
        else:
            message = handler.trick["message"].format(
                ingot_icon=handler.ingot_icon, amount=member.ingots
            )
            embed = handler._build_embed(
                message + handler._get_balance_message(member.nickname, 0)
            )
        embed.set_thumbnail(
            url=(
                "https://oldschool.runescape.wiki/images/thumb/"
                "Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png"
            )
        )
        return await interaction.followup.send(embed=embed)
