import logging
from typing import Optional
import discord
from reactionmenu import ViewButton, ViewMenu

from ironforgedbot.commands.hiscore.calculator import score_info
from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import (
    calculate_percentage,
    find_emoji,
    normalize_discord_string,
    validate_playername,
)
from ironforgedbot.common.ranks import (
    RANK_POINTS,
    RANKS,
    get_next_rank_from_points,
    get_rank_color_from_points,
    get_rank_from_points,
)
from ironforgedbot.common.responses import build_response_embed, send_error_response


logger = logging.getLogger(__name__)


async def cmd_breakdown(interaction: discord.Interaction, player: Optional[str] = None):
    """Compute player score with complete source enumeration.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        (optional) player: Runescape username to break down clan score for.
    """
    await interaction.response.defer(thinking=True)

    if player is None:
        player = interaction.user.display_name

    assert interaction.guild

    try:
        member, player = validate_playername(interaction.guild, player)
    except Exception as e:
        return await send_error_response(interaction, str(e))

    caller = normalize_discord_string(interaction.user.display_name)

    logger.info(f"Handling '/breakdown player:{player}' on behalf of '{caller}'")

    try:
        data = score_info(player)
    except RuntimeError as error:
        await send_error_response(interaction, str(error))
        return

    activities = data.clues + data.raids + data.bosses

    skill_points = 0
    for skill in data.skills:
        skill_points += skill["points"]

    activity_points = 0
    for activity in activities:
        activity_points += activity["points"]

    points_total = skill_points + activity_points
    rank_name = get_rank_from_points(points_total)
    rank_color = get_rank_color_from_points(points_total)
    rank_icon = find_emoji(interaction, rank_name)

    rank_breakdown_embed = build_response_embed(
        f"{rank_icon} {member.display_name} | Rank Ladder",
        "The **Iron Forged** player rank ladder.",
        rank_color,
    )

    for rank in RANKS:
        icon = find_emoji(interaction, rank)
        rank_point_threshold = RANK_POINTS[rank.upper()].value
        rank_breakdown_embed.add_field(
            name=(
                f"{icon} {rank}%s"
                % (
                    f"{EMPTY_SPACE}{EMPTY_SPACE}{EMPTY_SPACE}{EMPTY_SPACE}{EMPTY_SPACE}"
                    f"<-- _You are here_"
                    if rank == rank_name
                    else ""
                )
            ),
            value=f"{EMPTY_SPACE}{rank_point_threshold:,}+ points",
            inline=False,
        )

    if rank_name != RANKS.MYTH.value:
        next_rank_name = get_next_rank_from_points(points_total)
        next_rank_point_threshold = RANK_POINTS[next_rank_name.upper()].value
        next_rank_icon = find_emoji(interaction, next_rank_name)
        rank_breakdown_embed.add_field(
            name="Your Progress",
            value=(
                f"{rank_icon} -> {next_rank_icon} {points_total:,}/{next_rank_point_threshold:,} "
                f"({calculate_percentage(points_total, next_rank_point_threshold)}%)"
            ),
            inline=False,
        )

    skill_breakdown_embed = build_response_embed(
        f"{rank_icon} {member.display_name} | Skilling Points",
        f"Breakdown of **{skill_points:,}** points awarded for skill xp.",
        rank_color,
    )

    ordered_skills = sorted(data.skills, key=lambda x: x["display_order"])

    for skill in ordered_skills:
        skill_icon = find_emoji(interaction, skill["emoji_key"])
        skill_breakdown_embed.add_field(
            name=f"{skill_icon} {skill['points']:,} points",
            value=f"{EMPTY_SPACE}{skill['xp']:,} xp",
            inline=True,
        )

    # empty field to maintain layout
    skill_breakdown_embed.add_field(
        name="",
        value="",
        inline=True,
    )

    # There is a 25 field limit on embeds, so we need to paginate.
    # As not every player has kc on every boss we don't need to show
    # all bosses, so this won't be as bad for some players.
    field_count = 0
    boss_embeds = []

    working_embed = build_response_embed(
        "",
        "",
        rank_color,
    )

    boss_point_counter = 0
    for boss in data.bosses:
        if boss["points"] < 1:
            continue

        if field_count == 24:
            field_count = 0
            boss_embeds.append((working_embed))
            working_embed = build_response_embed(
                "",
                "",
                rank_color,
            )

        boss_point_counter += boss["points"]

        field_count += 1
        boss_icon = find_emoji(interaction, boss["emoji_key"])
        working_embed.add_field(
            name=f"{boss_icon} {boss['points']:,} points",
            value=f"{EMPTY_SPACE}{boss['kc']:,} kc",
        )

    boss_embeds.append(working_embed)
    boss_page_count = len(boss_embeds)

    for index, embed in enumerate(boss_embeds):
        embed.title = f"{rank_icon} {member.display_name} | Bossing Points"
        embed.description = (
            f"Breakdown of **{boss_point_counter:,}** points awarded for boss kc."
        )

        if boss_page_count > 1:
            embed.title = "".join(embed.title) + f" ({index + 1}/{boss_page_count})"

        if index + 1 == boss_page_count:
            if len(embed.fields) % 3 != 0:
                embed.add_field(name="", value="")

    raid_breakdown_embed = build_response_embed(
        f"{rank_icon} {member.display_name} | Raid Points",
        "",
        rank_color,
    )

    raid_point_counter = 0
    for raid in data.raids:
        raid_point_counter += raid["points"]
        raid_icon = find_emoji(interaction, raid["emoji_key"])
        raid_breakdown_embed.add_field(
            name=f"{raid_icon} {raid['points']:,} points",
            value=f"{EMPTY_SPACE}{raid['kc']:,} kc",
        )

    raid_breakdown_embed.description = (
        f"Breakdown of **{raid_point_counter:,}** points awarded for raid completions."
    )

    clue_breakdown_embed = build_response_embed(
        f"{rank_icon} {member.display_name} | Cluescroll Points",
        "Points awarded for cluescroll completions.",
        rank_color,
    )

    clue_point_counter = 0
    clue_icon = find_emoji(interaction, "cluescroll")
    for clue in data.clues:
        clue_point_counter += clue["points"]
        clue_breakdown_embed.add_field(
            name=f"{clue_icon} {clue['points']:,} points",
            value=f"{EMPTY_SPACE}{clue['kc']:,} {clue.get("display_name", clue['name'])}",
        )

    clue_breakdown_embed.description = f"Breakdown of **{clue_point_counter:,}** points awarded for cluescroll completions."

    menu = ViewMenu(
        interaction,
        menu_type=ViewMenu.TypeEmbed,
        show_page_director=True,
        timeout=600,
        delete_on_timeout=True,
    )

    menu.add_page(skill_breakdown_embed)
    for embed in boss_embeds:
        menu.add_page(embed)
    menu.add_page(raid_breakdown_embed)
    menu.add_page(clue_breakdown_embed)
    menu.add_page(rank_breakdown_embed)

    menu.add_button(ViewButton.back())
    menu.add_button(ViewButton.next())

    await menu.start()