import functools
import random
from typing import Any, List, Optional
from unittest.mock import AsyncMock, Mock
import discord
import wom
from ironforgedbot.commands.hiscore.calculator import ScoreBreakdown
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

mock_score_breakdown = ScoreBreakdown(
    skills=[
        {
            "name": "Slayer",
            "display_name": "Slayer",
            "display_order": 1,
            "emoji_key": "Slayer",
            "level": 67,
            "xp": 547953,
            "points": 18,
        }
    ],
    clues=[
        {
            "name": "Clue Scrolls (beginner)",
            "display_name": "Beginner",
            "display_order": 1,
            "emoji_key": "ClueScrolls_Beginner",
            "kc": 100,
            "points": 10,
        },
    ],
    raids=[
        {
            "name": "Tombs of Amascut",
            "display_order": 4,
            "emoji_key": "TombsOfAmascut",
            "kc": 10,
            "points": 10,
        },
    ],
    bosses=[
        {
            "name": "Kraken",
            "display_name": "Kraken",
            "display_order": 1,
            "emoji_key": "Kraken",
            "kc": 70,
            "points": 2,
        }
    ],
)


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
    interaction.guild = create_mock_discord_guild(members)
    interaction.user = user
    interaction.data = data

    if channel_id:
        interaction.channel_id = channel_id

    return interaction


def create_mock_discord_guild(
    members: Optional[List[discord.Member]] = None, roles: Optional[List[str]] = None
) -> discord.Guild:
    guild = Mock(spec=discord.Guild)
    guild.members = members or []
    guild.emojis = []
    guild.roles = []
    guild.member_count = len(members or [])
    if roles:
        for role in roles:
            guild.roles.append(create_mock_discord_role(role))

    return guild


def create_mock_discord_role(name: str) -> discord.Role:
    role = Mock(spec=discord.Role)
    role.name = name
    role.id = random.randint(100, 999)
    return role


def create_test_member(
    name: str, roles: list[str], nick: Optional[str] = None
) -> discord.Member:
    role_list = []
    for role in roles:
        mock_role = Mock(spec=discord.Role)
        mock_role.name = role
        role_list.append(mock_role)

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


def create_mock_wom_client() -> wom.Client:
    client = Mock(spec=wom.Client)
    client.start = AsyncMock()

    return client


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


def mock_rate_limit(rate: int, limit: int):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def mock_singleton():
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


def validate_embed(self, expected, actual):
    self.assertEqual(actual.title, expected.title)
    self.assertEqual(len(actual.fields), len(expected.fields))

    for expected, actual in zip(expected.fields, actual.fields):
        self.assertEqual(expected.name, actual.name)
        self.assertEqual(expected.value, actual.value)
        self.assertEqual(expected.inline, actual.inline)
