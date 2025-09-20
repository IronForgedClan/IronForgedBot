import functools
import random
from typing import Any, List, Optional
from unittest.mock import AsyncMock, Mock
import discord
from ironforgedbot.common.roles import ROLE

VALID_CONFIG = {
    "TEMP_DIR": "/tmp",
    "SHEET_ID": "1111",
    "GUILD_ID": "2222",
    "BOT_TOKEN": "aaaaa",
    "WOM_GROUP_ID": "3333",
    "WOM_API_KEY": "xxxxx",
    "AUTOMATION_CHANNEL_ID": "123456",
    "TRICK_OR_TREAT_ENABLED": "False",
    "TRICK_OR_TREAT_CHANNEL_ID": "",
    "RAFFLE_CHANNEL_ID": "123456",
}


def create_mock_discord_interaction(
    members: Optional[List[discord.Member]] = None,
    user: Optional[discord.Member] = None,
    channel_id: Optional[int] = None,
    data: Optional[Any] = None,
) -> discord.Interaction:
    if not members:
        members = []

    if not user:
        user = create_test_member("tester", [ROLE.MEMBER], "tester")

    members.append(user)
    interaction = Mock(spec=discord.Interaction)
    interaction.followup = AsyncMock()
    interaction.response = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.guild = create_mock_discord_guild(members)
    interaction.user = user
    interaction.user.id = getattr(user, 'id', 123456789)
    interaction.user.display_name = getattr(user, 'display_name', 'TestUser')
    interaction.data = data
    
    # Set up guild.get_member to return the user for role checking
    interaction.guild.get_member = Mock(return_value=user)

    if channel_id:
        interaction.channel_id = channel_id

    return interaction


def create_mock_discord_guild(
    members: Optional[List[discord.Member]] = None, roles: Optional[List[str]] = None
) -> discord.Guild:
    guild = Mock(spec=discord.Guild)
    guild.members = members or []
    guild.emojis = []
    guild.roles = [create_mock_discord_role(role) for role in (roles or [])]
    guild.member_count = len(guild.members)

    return guild


def create_mock_discord_role(name: str) -> discord.Role:
    role = Mock(spec=discord.Role)
    role.name = name
    role.id = random.randint(100, 999)
    return role


def create_test_member(
    name: str, roles: list[str], nick: Optional[str] = None
) -> discord.Member:
    role_list = [create_mock_discord_role(role) for role in roles]

    mock_member = Mock(spec=discord.Member)
    mock_member.bot = False
    mock_member.id = random.randint(100, 999)
    mock_member.roles = role_list
    mock_member.name = name
    mock_member.nick = nick
    mock_member.display_name = nick or name
    mock_member.add_roles = AsyncMock()
    mock_member.remove_roles = AsyncMock()

    return mock_member


def mock_require_role(role_name: str, ephemeral: Optional[bool] = False):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def mock_require_channel(channel_ids: list):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def get_url_status_code(session, url, timeout=5):
    try:
        async with session.get(url, timeout=timeout) as response:
            return response.status
    except Exception as e:
        return str(e)
