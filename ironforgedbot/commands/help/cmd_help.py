import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role


@require_role(ROLE.MEMBER)
async def cmd_help(interaction: discord.Interaction):
    """Display a list of available commands and what they do."""
    assert interaction.guild

    DWH_icon = find_emoji("DWH") or ""
    score_icon = find_emoji("Myth") or ""
    breakdown_icon = find_emoji("Mining") or ""
    ingot_icon = find_emoji("Ingot") or ""
    help_icon = "❓"

    embed = build_response_embed(
        title=f"{DWH_icon} Commands",
        description=(
            "Commands available to IronForged members. Just type the command "
            "to look yourself up or enter another user's name after the command to look them up."
        ),
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="/score",
        value=f"{score_icon} Show your or another player's clan score.",
        inline=False,
    )
    embed.add_field(
        name="/breakdown",
        value=f"{breakdown_icon} View detailed skill and activity point breakdown.",
        inline=False,
    )
    embed.add_field(
        name="/ingots",
        value=f"{ingot_icon} View your or another player's ingot balance.",
        inline=False,
    )
    embed.add_field(
        name="/help",
        value=f"{help_icon} List all commands available to members.",
        inline=False,
    )

    await interaction.followup.send(embed=embed)
