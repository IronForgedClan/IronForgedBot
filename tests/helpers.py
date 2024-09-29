import functools
import random
from typing import List, Optional
from unittest.mock import AsyncMock, Mock
import discord
import wom
from ironforgedbot.common.roles import ROLES

VALID_CONFIG = {
    "TEMP_DIR": "/tmp",
    "SHEET_ID": "1111",
    "GUILD_ID": "2222",
    "BOT_TOKEN": "aaaaa",
    "WOM_GROUP_ID": "3333",
    "WOM_API_KEY": "xxxxx",
    "AUTOMATION_CHANNEL_ID": "123456",
}


def create_mock_discord_interaction(
    members: Optional[List[discord.Member]] = None,
    user: Optional[discord.Member] = None,
) -> discord.Interaction:
    if not members:
        members = []

    if not user:
        user = create_test_member("tester", ROLES.MEMBER, "tester")

    interaction = Mock(spec=discord.Interaction)
    interaction.followup = AsyncMock()
    interaction.response = AsyncMock()
    interaction.guild = create_mock_discord_guild(members)
    interaction.user = user

    return interaction


def create_mock_discord_guild(
    members: Optional[List[discord.Member]] = None,
) -> discord.Guild:
    guild = Mock(spec=discord.Guild)
    guild.members = members or []
    guild.emojis = []
    return guild


def create_test_member(
    name: str, role: ROLES, nick: Optional[str] = None
) -> discord.Member:
    mock_role = Mock(spec=discord.Role)
    mock_role.name = role

    mock_member = Mock(spec=discord.Member)
    mock_member.id = random.randint(100, 999)
    mock_member.roles = [mock_role]
    mock_member.name = name
    mock_member.nick = nick
    mock_member.display_name = nick or name

    return mock_member


def create_mock_wom_client() -> wom.Client:
    client = Mock(spec=wom.Client)
    client.start = AsyncMock()

    return client


def mock_require_role(role_name: str, ephemeral: bool):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator
