import discord
from discord import app_commands


async def role_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function to show all guild roles filtered by current input."""
    guild = interaction.guild
    if not guild:
        return []

    choices = []
    for role in guild.roles:
        if (
            role != guild.default_role  # Exclude @everyone
            and not role.is_bot_managed()  # Exclude bot roles
            and current.lower() in role.name.lower()
        ):
            choices.append(app_commands.Choice(name=role.name, value=role.name))

    # Sort by position (higher roles first) and limit to 25
    choices.sort(
        key=lambda choice: next(
            (r.position for r in guild.roles if r.name == choice.value), 0
        ),
        reverse=True,
    )

    return choices[:25]