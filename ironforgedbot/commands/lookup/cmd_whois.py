import logging

import discord
import wom


from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import render_relative_time, validate_playername
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import require_role


logger = logging.getLogger(__name__)


@require_role(ROLES.ANY)
async def cmd_whois(interaction: discord.Interaction, player: str):
    """Get player's rsn history

    Arguments:
        interaction: Discord Interaction from CommandTree.
        player: Runescape username to get name history.
    """
    assert interaction.guild

    try:
        member, player = validate_playername(
            interaction.guild, player, must_be_member=False
        )
    except Exception as e:
        return await send_error_response(interaction, str(e))

    display_name = member.display_name if member is not None else player

    try:
        wom_client = wom.Client(api_key=CONFIG.WOM_API_KEY, user_agent="IronForged")
        await wom_client.start()
    except Exception as e:
        logger.critical(e)
        return await send_error_response(interaction, "Error connecting to api")

    result = await wom_client.players.get_name_changes(player)

    if not result.is_ok:
        return await send_error_response(
            interaction, "Error retrieving name change history"
        )

    embed = build_response_embed(
        f"📋 {display_name} | Name History",
        "",
        discord.Colour.purple(),
    )

    details = result.unwrap()

    if len(details) <= 0:
        embed.add_field(
            name="",
            value="No name changes for this user found.",
            inline=False,
        )
    else:
        for change in details:
            if not change.status == "approved":
                continue

            if change.resolved_at is not None:
                resolved = render_relative_time(change.resolved_at)
            else:
                resolved = "pending"

            embed.add_field(
                name="",
                value=f"_{resolved}_: {change.old_name} → **{change.new_name}**",
                inline=False,
            )
            print(change)

    await interaction.followup.send(embed=embed)
    await wom_client.close()
