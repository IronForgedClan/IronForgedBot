import discord
from discord import app_commands

from ironforgedbot.common.helpers import normalize_discord_string


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


async def member_nickname_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function to show guild member nicknames filtered by current input."""
    guild = interaction.guild
    if not guild or not guild.members:
        return []

    current_lower = current.lower()
    choices = []

    for member in guild.members:
        if not member.nick or len(member.nick) < 1:
            continue

        display_name = member.display_name
        normalized_name = normalize_discord_string(display_name)

        if current_lower in normalized_name.lower():
            choices.append(app_commands.Choice(name=display_name, value=display_name))

    # Sort alphabetically by display name and limit to 25
    choices.sort(key=lambda choice: choice.name.lower())
    return choices[:25]
