import logging

import discord
from discord import app_commands
from reactionmenu import ViewButton, ViewMenu

from ironforgedbot.commands.hiscore.score_utils import _calculate_points
from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import (
    find_emoji,
    normalize_discord_string,
    render_percentage,
    validate_playername,
)
from ironforgedbot.config import CONFIG
from ironforgedbot.common.ranks import (
    RANK_POINTS,
    RANK,
    get_god_alignment_from_member,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.responses import (
    build_response_embed,
    send_error_response,
    send_member_no_hiscore_values,
    send_not_clan_member,
    send_prospect_response,
)
from ironforgedbot.common.roles import ROLE, has_prospect_role
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.text_formatters import text_italic
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.http import HTTP, HttpException
from ironforgedbot.models.score import ActivityScore, ScoreBreakdown
from ironforgedbot.services.score_service import get_score_service

logger = logging.getLogger(__name__)

_EMBED_TIMEOUT = 60
_BOSS_FIELDS_PER_PAGE = 24
_BOSS_COLUMNS = 3
_RANK_ARROW_PADDING = EMPTY_SPACE * 7
_BREAKDOWN_TITLE = "ℹ️ Breakdown"

_BREAKDOWN_STATIC_DESCRIPTION = (
    "Points are earned through in-game achievements and determine your clan rank. "
    f"See <#{CONFIG.RANKINGS_CHANNEL_ID}> for more information."
)


def _build_embed_description(
    rank_icon: str,
    display_name: str,
    points_total: int,
    points_label: str | None = None,
    points_value: int | None = None,
) -> str:
    """Build the standard breakdown embed description.

    Args:
        rank_icon: Emoji for the player's current rank.
        display_name: The player's display name (should be normalized before passing).
        points_total: The player's overall point total across all categories.
        points_label: Label for the category points column e.g. "Skilling Points".
        points_value: The point total for this category.
    """
    if points_label is not None and points_value is not None:
        percentage = render_percentage(points_value, points_total)
        return (
            f"{_BREAKDOWN_STATIC_DESCRIPTION}\n\n"
            f"**Member:** {rank_icon} {display_name}\n"
            f"**{points_label}:** {points_value:,}/{points_total:,} ({percentage})\n{EMPTY_SPACE}"
        )
    return (
        f"{_BREAKDOWN_STATIC_DESCRIPTION}\n\n"
        f"**Member:** {rank_icon} {display_name}\n"
        f"**Total Points:** {points_total:,}\n{EMPTY_SPACE}"
    )


def _build_rank_ladder_embed(
    display_name: str,
    rank_name: str,
    rank_icon: str,
    rank_color: discord.Color,
    points_total: int,
    god_alignment: str | None,
) -> discord.Embed:
    """Build the rank ladder embed showing all ranks and current player progress.

    Args:
        display_name: The player's display name.
        rank_name: The player's current rank name.
        rank_icon: Emoji for the player's current rank.
        rank_color: Discord color for the embed.
        points_total: The player's total points.
        god_alignment: God alignment string if at GOD rank, else None.
    """
    embed = build_response_embed(
        f"{_BREAKDOWN_TITLE} - Rank Ladder",
        _build_embed_description(
            rank_icon,
            normalize_discord_string(display_name),
            points_total,
        ),
        rank_color,
    )

    display_ranks = [r for r in RANK if not r.lower().startswith("god_")]
    for rank in display_ranks:
        icon = find_emoji(rank)
        point_threshold = RANK_POINTS[rank.upper()]
        arrow = (
            f"{_RANK_ARROW_PADDING}← {text_italic(normalize_discord_string(display_name))}"
            if rank == rank_name
            else ""
        )
        embed.add_field(
            name=f"{icon} {rank}{arrow}",
            value=f"{EMPTY_SPACE}{point_threshold:,}+ points",
            inline=False,
        )

    if rank_name == RANK.GOD:
        alignment_value = (
            f"{rank_icon} {god_alignment} ({find_emoji(god_alignment)})"
            if god_alignment
            else f"{find_emoji('God')} Unaligned!"
        )
        embed.add_field(name="God Alignment", value=alignment_value, inline=False)
    else:
        rank_point_threshold = RANK_POINTS[rank_name.upper()]
        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()]
        next_rank_icon = find_emoji(next_rank_name)
        percentage = render_percentage(
            points_total - int(rank_point_threshold),
            int(next_rank_point_threshold) - int(rank_point_threshold),
        )
        embed.add_field(
            name="Your Progress",
            value=f"{rank_icon} → {next_rank_icon} {points_total:,}/{next_rank_point_threshold:,} ({percentage})",
            inline=False,
        )

    return embed


def _build_boss_embeds(
    bosses: list[ActivityScore],
    rank_icon: str,
    rank_color: discord.Color,
    display_name: str,
    points_total: int,
) -> list[discord.Embed]:
    """Build paginated boss embeds, one page per _BOSS_FIELDS_PER_PAGE bosses.

    Bosses with zero points are excluded. The last page is padded to maintain
    the three-column layout.

    Args:
        bosses: List of boss ActivityScore objects.
        rank_icon: Emoji for the player's current rank.
        rank_color: Discord color for the embeds.
        display_name: The player's display name.
        points_total: The player's overall point total across all categories.
    """
    embeds: list[discord.Embed] = []
    boss_point_counter = 0
    field_count = 0

    working_embed = build_response_embed("", "", rank_color)

    for boss in bosses:
        if boss.points < 1:
            continue

        if field_count == _BOSS_FIELDS_PER_PAGE:
            field_count = 0
            embeds.append(working_embed)
            working_embed = build_response_embed("", "", rank_color)

        boss_point_counter += boss.points
        field_count += 1
        boss_icon = find_emoji(boss.emoji_key)
        working_embed.add_field(
            name=f"{boss_icon} {boss.points:,} points",
            value=f"{EMPTY_SPACE}{boss.kc:,} kc",
        )

    embeds.append(working_embed)
    page_count = len(embeds)

    for index, embed in enumerate(embeds):
        embed.title = f"{_BREAKDOWN_TITLE} - Bossing"
        embed.description = _build_embed_description(
            rank_icon,
            normalize_discord_string(display_name),
            points_total,
            "Bossing Points",
            boss_point_counter,
        )

        if page_count > 1:
            embed.title += f" ({index + 1}/{page_count})"

        if index + 1 == page_count:
            while len(embed.fields) % _BOSS_COLUMNS != 0:
                embed.add_field(name="", value="")

    return embeds


def _build_activity_embed(
    title: str,
    items: list[ActivityScore],
    points_label: str,
    rank_icon: str,
    rank_color: discord.Color,
    display_name: str,
    points_total: int,
    value_formatter: callable,
) -> discord.Embed:
    """Build a single-page activity breakdown embed (raids, clues, etc.).

    Args:
        title: Embed title suffix e.g. "Raids".
        items: List of ActivityScore objects to display.
        points_label: Label for the category points column e.g. "Raid Points".
        rank_icon: Emoji for the player's current rank.
        rank_color: Discord color for the embed.
        display_name: The player's display name.
        points_total: The player's overall point total across all categories.
        value_formatter: Callable(item) -> str for the field value text.
    """
    category_points = sum(item.points for item in items)
    embed = build_response_embed(
        f"{_BREAKDOWN_TITLE} - {title}",
        _build_embed_description(
            rank_icon,
            normalize_discord_string(display_name),
            points_total,
            points_label,
            category_points,
        ),
        rank_color,
    )
    for item in items:
        icon = find_emoji(item.emoji_key)
        embed.add_field(
            name=f"{icon} {item.points:,} points",
            value=value_formatter(item),
        )
    return embed


def _resolve_rank_display(
    member: discord.Member | None,
    points_total: int,
    rank_name: str,
) -> tuple[str, discord.Color, str | None]:
    """Resolve rank icon, embed color, and god alignment for a player.

    Args:
        member: The Discord member, or None if not in the clan.
        points_total: The player's total points.
        rank_name: The player's current rank name.

    Returns:
        Tuple of (rank_icon, rank_color, god_alignment).
        god_alignment is None for non-GOD ranks.
    """
    if rank_name == RANK.GOD:
        god_alignment = get_god_alignment_from_member(member)
        rank_color = get_rank_color_from_points(points_total, god_alignment)
        rank_icon = find_emoji(god_alignment or rank_name)
        return rank_icon, rank_color, god_alignment
    return find_emoji(rank_name), get_rank_color_from_points(points_total), None


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
@app_commands.describe(
    player="Player name to break down score for (defaults to your nickname)"
)
async def cmd_breakdown(interaction: discord.Interaction, player: str | None = None):
    """Compute player score with complete source enumeration.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        (optional) player: Runescape username to break down clan score for.
    """
    if player is None:
        player = interaction.user.display_name

    assert interaction.guild

    try:
        member, player = validate_playername(
            interaction.guild, player, must_be_member=False
        )
    except Exception as e:
        return await send_error_response(interaction, str(e), report_to_channel=False)

    display_name = member.display_name if member is not None else player
    service = get_score_service(HTTP)

    try:
        data = await service.get_player_score(player)
    except (HiscoresError, HttpException):
        return await send_error_response(
            interaction,
            "An error has occurred calculating the score for this user. Please try again.",
        )
    except HiscoresNotFound:
        if member:
            return await send_member_no_hiscore_values(interaction, display_name)
        else:
            data = ScoreBreakdown([], [], [], [])

    skill_points, activity_points, points_total = _calculate_points(data)
    rank_name = get_rank_from_points(points_total)
    rank_icon, rank_color, god_alignment = _resolve_rank_display(
        member, points_total, rank_name
    )

    if member and member.roles:
        if has_prospect_role(member):
            return await send_prospect_response(
                interaction, rank_name, rank_icon, member
            )

    if not member:
        return await send_not_clan_member(
            interaction,
            rank_name,
            rank_icon,
            rank_color,
            points_total,
            display_name,
        )

    skill_breakdown_embed = build_response_embed(
        f"{_BREAKDOWN_TITLE} - Skilling",
        _build_embed_description(
            rank_icon,
            normalize_discord_string(display_name),
            points_total,
            "Skilling Points",
            skill_points,
        ),
        rank_color,
    )

    ordered_skills = sorted(data.skills, key=lambda x: x.display_order)
    for skill in ordered_skills:
        skill_icon = find_emoji(skill.emoji_key)
        skill_breakdown_embed.add_field(
            name=f"{skill_icon} {skill.points:,} points",
            value=f"{EMPTY_SPACE}{skill.xp:,} xp",
            inline=True,
        )

    # Empty field to maintain three-column layout
    skill_breakdown_embed.add_field(name="", value="", inline=True)

    boss_embeds = _build_boss_embeds(
        data.bosses, rank_icon, rank_color, display_name, points_total
    )

    raid_breakdown_embed = _build_activity_embed(
        "Raids",
        data.raids,
        "Raid Points",
        rank_icon,
        rank_color,
        display_name,
        points_total,
        lambda r: f"{EMPTY_SPACE}{r.kc:,} kc",
    )

    clue_breakdown_embed = _build_activity_embed(
        "Clues",
        data.clues,
        "Clue Points",
        rank_icon,
        rank_color,
        display_name,
        points_total,
        lambda c: f"{EMPTY_SPACE}{c.kc:,} {c.display_name or c.name}",
    )

    rank_ladder_embed = _build_rank_ladder_embed(
        display_name, rank_name, rank_icon, rank_color, points_total, god_alignment
    )

    all_embeds = (
        [skill_breakdown_embed]
        + boss_embeds
        + [raid_breakdown_embed, clue_breakdown_embed, rank_ladder_embed]
    )

    menu = ViewMenu(
        interaction,
        menu_type=ViewMenu.TypeEmbed,
        show_page_director=False,
        timeout=_EMBED_TIMEOUT,
        delete_on_timeout=True,
    )

    for embed in all_embeds:
        menu.add_page(embed)

    menu.add_button(
        ViewButton(
            style=discord.ButtonStyle.primary,
            label="← Back",
            custom_id=ViewButton.ID_PREVIOUS_PAGE,
        )
    )
    menu.add_button(
        ViewButton(
            style=discord.ButtonStyle.primary,
            label="Next →",
            custom_id=ViewButton.ID_NEXT_PAGE,
        )
    )
    menu.add_button(
        ViewButton(
            style=discord.ButtonStyle.danger,
            label="⨯ Close",
            custom_id=ViewButton.ID_END_SESSION,
        )
    )

    try:
        await menu.start()
    except Exception as e:
        logger.error(f"Error starting breakdown menu: {e}", exc_info=True)
        try:
            await menu.stop()
        except Exception as stop_error:
            logger.debug(f"Error stopping breakdown menu: {stop_error}")
        await send_error_response(
            interaction,
            "An unexpected error occurred while generating the breakdown. Please try again.",
        )
