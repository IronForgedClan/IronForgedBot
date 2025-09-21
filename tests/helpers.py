import functools
import itertools
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

_id_counter = itertools.count(100000)


def create_mock_discord_interaction(
    members: Optional[List[discord.Member]] = None,
    user: Optional[discord.Member] = None,
    channel_id: Optional[int] = None,
    data: Optional[Any] = None,
) -> discord.Interaction:
    members_list = list(members) if members else []

    if not user:
        user = create_test_member("tester", [ROLE.MEMBER], "tester")

    members_list.append(user)
    interaction = Mock(spec=discord.Interaction)
    interaction.id = next(_id_counter)
    interaction.followup = AsyncMock()
    interaction.response = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.guild = create_mock_discord_guild(members_list)
    interaction.user = user
    interaction.data = data
    interaction.token = "mock_token"
    interaction.application_id = next(_id_counter)

    # Set up guild.get_member to return the user for role checking
    interaction.guild.get_member = Mock(return_value=user)

    if channel_id:
        interaction.channel_id = channel_id
        interaction.channel = Mock()
        interaction.channel.id = channel_id
    else:
        interaction.channel_id = next(_id_counter)
        interaction.channel = Mock()
        interaction.channel.id = interaction.channel_id

    return interaction


def create_mock_discord_guild(
    members: Optional[List[discord.Member]] = None, roles: Optional[List[str]] = None
) -> discord.Guild:
    guild = Mock(spec=discord.Guild)
    guild.id = next(_id_counter)
    guild.name = "Test Guild"
    guild.members = members or []
    guild.emojis = []
    guild.roles = [create_mock_discord_role(role) for role in (roles or [])]
    guild.member_count = len(guild.members)
    guild.get_member = Mock(return_value=None)
    guild.get_role = Mock(return_value=None)
    guild.get_channel = Mock(return_value=None)

    return guild


def create_mock_discord_role(name: str) -> discord.Role:
    role = Mock(spec=discord.Role)
    role.name = name
    role.id = next(_id_counter)
    role.mention = f"<@&{role.id}>"
    role.position = 0
    role.permissions = Mock()
    return role


def create_test_member(
    name: str, roles: List[str], nick: Optional[str] = None
) -> discord.Member:
    role_list = [create_mock_discord_role(role) for role in roles]

    mock_member = Mock(spec=discord.Member)
    mock_member.bot = False
    mock_member.id = next(_id_counter)
    mock_member.roles = role_list
    mock_member.name = name
    mock_member.nick = nick
    mock_member.display_name = nick or name
    mock_member.mention = f"<@{mock_member.id}>"
    mock_member.avatar = None
    mock_member.joined_at = None
    mock_member.add_roles = AsyncMock()
    mock_member.remove_roles = AsyncMock()
    mock_member.edit = AsyncMock()

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


def setup_database_service_mocks(
    mock_db, mock_service_factory, mock_service_instance=None
):
    """Sets up common database and service mocking pattern used across many tests.
    
    Args:
        mock_db: Mock of the database module
        mock_service_factory: Mock of the service factory function (e.g., create_ingot_service)
        mock_service_instance: Optional mock service instance to return
    """
    mock_session = AsyncMock()

    # Set up the async context manager pattern
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_session
    mock_context_manager.__aexit__.return_value = None
    mock_db.get_session.return_value = mock_context_manager

    if mock_service_instance is None:
        mock_service_instance = AsyncMock()
    
    # For factory functions, we set the return value directly
    mock_service_factory.return_value = mock_service_instance

    return mock_session, mock_service_instance


def assert_embed_structure(
    test_case,
    interaction_mock,
    expected_title=None,
    expected_description=None,
    expected_field_count=None,
    expected_color=None,
    expected_fields=None,
):
    """Validates common embed properties sent via interaction.followup.send."""
    interaction_mock.followup.send.assert_called_once()
    call_args = interaction_mock.followup.send.call_args

    # Check embed was sent
    test_case.assertIn("embed", call_args.kwargs)
    embed = call_args.kwargs["embed"]

    if expected_title is not None:
        test_case.assertEqual(embed.title, expected_title)

    if expected_description is not None:
        test_case.assertEqual(embed.description, expected_description)

    if expected_color is not None:
        test_case.assertEqual(embed.color, expected_color)

    if expected_field_count is not None:
        test_case.assertEqual(len(embed.fields), expected_field_count)

    if expected_fields is not None:
        for i, (name, value, inline) in enumerate(expected_fields):
            test_case.assertEqual(embed.fields[i].name, name)
            test_case.assertEqual(embed.fields[i].value, value)
            test_case.assertEqual(embed.fields[i].inline, inline)

    return embed


def assert_error_response_sent(test_case, interaction_mock, expected_error_message):
    """Validates that send_error_response was called with expected message."""
    # This assumes send_error_response was mocked in the test
    # The actual mock object should be passed or accessed via the test
    test_case.assertTrue(interaction_mock.followup.send.called)
    call_args = interaction_mock.followup.send.call_args

    if "embed" in call_args.kwargs:
        embed = call_args.kwargs["embed"]
        test_case.assertIn(expected_error_message, embed.description)


def assert_followup_called_with_embed(
    test_case, interaction_mock, embed_title=None, has_file=False, call_count=1
):
    """Validates interaction.followup.send was called with expected parameters."""
    if call_count == 1:
        interaction_mock.followup.send.assert_called_once()
    else:
        test_case.assertEqual(interaction_mock.followup.send.call_count, call_count)

    call_args = interaction_mock.followup.send.call_args

    if has_file:
        test_case.assertIn("file", call_args.kwargs)

    if embed_title is not None:
        test_case.assertIn("embed", call_args.kwargs)
        embed = call_args.kwargs["embed"]
        test_case.assertEqual(embed.title, embed_title)

    return call_args


def create_test_db_member(
    nickname="TestUser",
    discord_id=None,
    rank="Iron",
    ingots=1000,
    active=True,
    joined_date=None,
    **kwargs,
):
    """Creates test Member model instance with common defaults."""
    from unittest.mock import Mock
    from datetime import datetime, timezone

    member = Mock()
    # If id is provided in kwargs, use it, otherwise generate a string ID
    if "id" in kwargs:
        member.id = kwargs.pop("id")
    else:
        member.id = f"test-member-{next(_id_counter)}"

    member.nickname = nickname
    member.discord_id = discord_id or next(_id_counter)
    member.rank = rank
    member.ingots = ingots
    member.active = active
    member.joined_date = joined_date or datetime.now(timezone.utc)

    # Apply any additional kwargs
    for key, value in kwargs.items():
        setattr(member, key, value)

    return member


def create_wom_response_mock(
    status=200,
    skills_data=None,
    activities_data=None,
    player_data=None,
    name_changes_data=None,
):
    """Creates standardized WOM API response mock."""
    mock_response = Mock()
    mock_response.status = status

    if skills_data is not None:
        mock_response.body = {"skills": skills_data}
    elif activities_data is not None:
        mock_response.body = {"activities": activities_data}
    elif player_data is not None:
        mock_response.body = player_data
    elif name_changes_data is not None:
        mock_response.body = name_changes_data
    else:
        mock_response.body = {}

    return mock_response


def setup_time_mocks(
    mock_datetime, mock_time, fixed_datetime=None, duration_seconds=5.0
):
    """Sets up standard time mocking pattern for consistent testing."""
    from datetime import datetime, timezone

    if fixed_datetime is None:
        fixed_datetime = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    if mock_datetime:
        mock_datetime.now.return_value = fixed_datetime
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

    if mock_time:
        mock_time.perf_counter.side_effect = [0.0, duration_seconds]

    return fixed_datetime


def create_test_score_data(skills_count=2, activities_count=2, total_points=1500):
    """Creates standardized score test data for skill/activity calculations."""
    from unittest.mock import Mock

    # Create sample skills with proper sorting attributes
    skills = []
    for i in range(skills_count):
        skill = Mock()
        skill.name = f"Skill{i+1}"
        skill.group = None
        skill.id = i + 1
        skill.canonical_name = f"Skill{i+1}"
        skill.experience = 13034000 - (i * 1000000)
        skill.xp = skill.experience  # Add xp alias for compatibility
        skill.level = 99 - (i * 5)
        skill.points = 1000 - (i * 100)
        skill.display_order = i + 1  # Add for sorting
        # Create proper comparison methods
        skill._display_order = i + 1

        def make_lt(order):
            return lambda other: order < other._display_order

        def make_gt(order):
            return lambda other: order > other._display_order

        def make_eq(order):
            return lambda other: order == other._display_order

        skill.__lt__ = make_lt(i + 1)
        skill.__gt__ = make_gt(i + 1)
        skill.__eq__ = make_eq(i + 1)
        skills.append(skill)

    # Create sample activities with proper sorting attributes
    activities = []
    for i in range(activities_count):
        activity = Mock()
        activity.name = f"Activity{i+1}"
        activity.group = None
        activity.id = i + 1
        activity.canonical_name = f"Activity{i+1}"
        activity.count = 200 - (i * 50)
        activity.score = activity.count  # Add score alias for compatibility
        activity.kc = activity.count  # Add kc alias for compatibility
        activity.points = 100 - (i * 25)
        activity.display_order = i + 1  # Add for sorting
        # Create proper comparison methods
        activity._display_order = i + 1

        def make_lt(order):
            return lambda other: order < other._display_order

        def make_gt(order):
            return lambda other: order > other._display_order

        def make_eq(order):
            return lambda other: order == other._display_order

        activity.__lt__ = make_lt(i + 1)
        activity.__gt__ = make_gt(i + 1)
        activity.__eq__ = make_eq(i + 1)
        activities.append(activity)

    # Create breakdown mock
    breakdown = Mock()
    breakdown.skills = skills
    breakdown.clues = activities[:1] if activities else []
    breakdown.raids = activities[1:2] if len(activities) > 1 else []
    breakdown.bosses = (
        activities[2:] if len(activities) > 2 else activities[-1:] if activities else []
    )

    return breakdown


def create_test_member_with_scores(
    nickname="TestUser", discord_id=None, rank="Iron", total_points=1500, **kwargs
):
    """Creates a test member with associated score data."""
    member = create_test_db_member(nickname, discord_id, rank, **kwargs)
    member.total_points = total_points
    member.score_breakdown = create_test_score_data()
    return member


def create_test_score_breakdown(skills_count=2, activities_count=2):
    """Creates real ScoreBreakdown object for cache serialization testing."""
    from ironforgedbot.models.score import ScoreBreakdown, SkillScore, ActivityScore

    skills = []
    for i in range(skills_count):
        skill = SkillScore(
            name=f"Skill{i+1}",
            display_name=f"Skill {i+1}",
            display_order=i + 1,
            emoji_key=f"skill_{i+1}",
            xp=13034000 - (i * 1000000),
            level=99 - (i * 5),
            points=1000 - (i * 100),
        )
        skills.append(skill)

    clues = []
    raids = []
    bosses = []

    for i in range(min(activities_count, 1)):
        clue = ActivityScore(
            name=f"Clue{i+1}",
            display_name=f"Clue {i+1}",
            display_order=i + 1,
            emoji_key=f"clue_{i+1}",
            kc=200 - (i * 50),
            points=100 - (i * 25),
        )
        clues.append(clue)

    for i in range(min(activities_count, 1)):
        raid = ActivityScore(
            name=f"Raid{i+1}",
            display_name=f"Raid {i+1}",
            display_order=i + 1,
            emoji_key=f"raid_{i+1}",
            kc=150 - (i * 30),
            points=75 - (i * 15),
        )
        raids.append(raid)

    for i in range(max(0, activities_count - 2)):
        boss = ActivityScore(
            name=f"Boss{i+1}",
            display_name=f"Boss {i+1}",
            display_order=i + 1,
            emoji_key=f"boss_{i+1}",
            kc=100 - (i * 20),
            points=50 - (i * 10),
        )
        bosses.append(boss)

    return ScoreBreakdown(skills=skills, clues=clues, raids=raids, bosses=bosses)
