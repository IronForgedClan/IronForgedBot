import discord
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.decorators import require_role
from ironforgedbot.common.roles import ROLE


@require_role(ROLE.MEMBER)
async def cmd_help(interaction: discord.Interaction):
    """Display a list of available commands and what they do."""

    assert interaction.guild

    help_text = (
        "**Available Commands:**\n"
        "• `/score [player]` - Show a player's clan score.\n"
        "• `/breakdown [player]` - Show a player's point breakdown from skills and activities.\n"
        "• `/ingots [player]` - Show a player's current ingot amount.\n"
        "• `/help` - Show this help message.\n"
    )

    embed = build_response_embed(
        title="IronForged Bot Help",
        description=help_text,
        color=discord.Color.blurple(),
    )

    await interaction.followup.send(embed=embed)
