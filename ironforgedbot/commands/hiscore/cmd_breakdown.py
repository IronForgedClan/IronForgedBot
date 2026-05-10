import logging
from typing import List

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

_BOSS_FIELDS_PER_PAGE = 24
_BOSS_COLUMNS = 3
_RANK_ARROW_PADDING = EMPTY_SPACE * 7
_BREAKDOWN_TITLE = "ℹ️ Breakdown"
_BREAKDOWN_EMBED_DESCRIPTION = (
    "Points are earned through in-game achievements and determine your clan rank. "
    f"See <#{CONFIG.RANKINGS_CHANNEL_ID}> for more information."
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
        _BREAKDOWN_EMBED_DESCRIPTION,
        rank_color,
    )

    embed.add_field(
        name="Member",
        value=f"{rank_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )
    embed.add_field(name="Total Points", value=f"{points_total:,}", inline=True)
    embed.add_field(name="", value="", inline=True)

    display_ranks = [r for r in RANK if not r.lower().startswith("god_")]
    for rank in display_ranks:
        icon = find_emoji(rank)
        point_threshold = RANK_POINTS[rank.upper()]
        arrow = (
            f"{_RANK_ARROW_PADDING}← {text_italic(display_name)}"
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
    bosses: List[ActivityScore],
    rank_icon: str,
    rank_color: discord.Color,
    display_name: str,
) -> list[discord.Embed]:
    """Build paginated boss embeds, one page per _BOSS_FIELDS_PER_PAGE bosses.

    Bosses with zero points are excluded. The last page is padded to maintain
    the three-column layout.

    Args:
        bosses: List of boss ActivityScore objects.
        rank_icon: Emoji for the player's current rank.
        rank_color: Discord color for the embeds.
        display_name: The player's display name.
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
        embed.description = _BREAKDOWN_EMBED_DESCRIPTION

        if page_count > 1:
            embed.title += f" ({index + 1}/{page_count})"

        embed.add_field(
            name="Member",
            value=f"{rank_icon} {normalize_discord_string(display_name)}",
            inline=True,
        )
        embed.add_field(name="Bossing Points", value=f"{boss_point_counter:,}", inline=True)
        embed.add_field(name="", value="", inline=True)

        if index + 1 == page_count:
            if len(embed.fields) % _BOSS_COLUMNS != 0:
                embed.add_field(name="", value="")

    return embeds


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
        return await send_error_response(
            interaction, str(e), report_to_channel=False
        )

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

    god_alignment = None
    if rank_name == RANK.GOD:
        god_alignment = get_god_alignment_from_member(member)
        rank_color = get_rank_color_from_points(points_total, god_alignment)
        rank_icon = find_emoji(god_alignment or rank_name)
    else:
        rank_color = get_rank_color_from_points(points_total)
        rank_icon = find_emoji(rank_name)

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
        _BREAKDOWN_EMBED_DESCRIPTION,
        rank_color,
    )
    skill_breakdown_embed.add_field(
        name="Member",
        value=f"{rank_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )
    skill_breakdown_embed.add_field(
        name="Skilling Points", value=f"{skill_points:,}", inline=True
    )
    skill_breakdown_embed.add_field(name="", value="", inline=True)

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

    boss_embeds = _build_boss_embeds(data.bosses, rank_icon, rank_color, display_name)

    raid_point_counter = sum(r.points for r in data.raids)
    raid_breakdown_embed = build_response_embed(
        f"{_BREAKDOWN_TITLE} - Raids",
        _BREAKDOWN_EMBED_DESCRIPTION,
        rank_color,
    )
    raid_breakdown_embed.add_field(
        name="Member",
        value=f"{rank_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )
    raid_breakdown_embed.add_field(
        name="Raid Points", value=f"{raid_point_counter:,}", inline=True
    )
    raid_breakdown_embed.add_field(name="", value="", inline=True)
    for raid in data.raids:
        raid_icon = find_emoji(raid.emoji_key)
        raid_breakdown_embed.add_field(
            name=f"{raid_icon} {raid.points:,} points",
            value=f"{EMPTY_SPACE}{raid.kc:,} kc",
        )

    clue_point_counter = sum(c.points for c in data.clues)
    clue_breakdown_embed = build_response_embed(
        f"{_BREAKDOWN_TITLE} - Clues",
        _BREAKDOWN_EMBED_DESCRIPTION,
        rank_color,
    )
    clue_breakdown_embed.add_field(
        name="Member",
        value=f"{rank_icon} {normalize_discord_string(display_name)}",
        inline=True,
    )
    clue_breakdown_embed.add_field(
        name="Clue Points", value=f"{clue_point_counter:,}", inline=True
    )
    clue_breakdown_embed.add_field(name="", value="", inline=True)
    for clue in data.clues:
        clue_icon = find_emoji(clue.emoji_key)
        clue_breakdown_embed.add_field(
            name=f"{clue_icon} {clue.points:,} points",
            value=f"{EMPTY_SPACE}{clue.kc:,} {clue.display_name or clue.name}",
        )

    rank_ladder_embed = _build_rank_ladder_embed(
        display_name, rank_name, rank_icon, rank_color, points_total, god_alignment
    )

    menu = ViewMenu(
        interaction,
        menu_type=ViewMenu.TypeEmbed,
        show_page_director=True,
        timeout=300,
        delete_on_timeout=True,
    )

    menu.add_page(skill_breakdown_embed)
    for embed in boss_embeds:
        menu.add_page(embed)
    menu.add_page(raid_breakdown_embed)
    menu.add_page(clue_breakdown_embed)
    menu.add_page(rank_ladder_embed)

    menu.add_button(ViewButton.back())
    menu.add_button(ViewButton.next())
    menu.add_button(ViewButton.end_session())

    try:
        await menu.start()
    except Exception as e:
        logger.error(f"Error starting breakdown menu: {e}", exc_info=True)
        try:
            await menu.stop()
        except Exception:
            pass
        await send_error_response(
            interaction,
            "An unexpected error occurred while generating the breakdown. Please try again.",
        )
