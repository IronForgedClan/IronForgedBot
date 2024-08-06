import random
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock
import discord
from ironforgedbot.common.roles import ROLES


def create_mock_discord_interaction(
    members: Optional[List[discord.User]] = None,
) -> discord.Interaction:
    if not members:
        members = []

    interaction = MagicMock(spec=discord.Interaction)
    interaction.followup = AsyncMock()
    interaction.response = AsyncMock()
    interaction.guild.members = members

    return interaction


def create_test_member(name: str, role: ROLES, nick=None) -> discord.User:
    if nick is None:
        nick = name

    discord_role = MagicMock(spec=discord.Role)
    discord_role.name = role

    user = MagicMock(spec=discord.User)
    user.id = random.randint(100, 999)
    user.roles = [role]
    user.name = name
    user.nick = nick
    user.display_name = nick

    return user
