import discord

from ironforgedbot.common.helpers import find_emoji


async def send_error_response(interaction: discord.Interaction, message: str):
    embed = discord.Embed(
        title=":exclamation: Error", description=message, color=discord.Colour.red()
    )

    await interaction.followup.send(embed=embed)


def build_error_message_string(message: str) -> str:
    return f":warning:\n{message}"


def build_response_embed(
    title: str, description: str, color: discord.Color
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


async def send_prospect_response(
    interaction: discord.Interaction,
    eligible_rank_name: str,
    eligible_rank_icon: str,
    member: discord.Member,
):
    prospect_icon = find_emoji(interaction, "Prospect")
    embed_description = (
        f'The member "_{member.display_name}_" is a **{prospect_icon} Prospect**, and will\n'
        f"be eligible for **{eligible_rank_icon} {eligible_rank_name}** rank once their **14 day**\n"
        "probationary period is over."
    )
    embed = build_response_embed(
        "",
        embed_description,
        discord.Color.from_str("#df781c"),
    )

    await interaction.followup.send(embed=embed)
