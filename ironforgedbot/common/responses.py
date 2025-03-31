from datetime import datetime, timedelta, timezone
import logging
import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.ranks import get_rank_color_from_points, get_rank_from_points
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold, text_sub
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.tasks.job_refresh_ranks import PROBATION_DAYS
from ironforgedbot.database.database import db

logger = logging.getLogger(__name__)


async def send_error_response(interaction: discord.Interaction, message: str):
    embed = discord.Embed(
        title=":exclamation: Error", description=message, color=discord.Colour.red()
    )

    await interaction.followup.send(embed=embed)


def build_error_message_string(message: str) -> str:
    return f":warning:\n{message}"


def build_response_embed(
    title: str, description: str, color: discord.Color
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def build_ingot_response_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, color=discord.Colour.light_grey()
    )


async def send_prospect_response(
    interaction: discord.Interaction,
    eligible_rank_name: str,
    eligible_rank_icon: str,
    member: discord.Member,
):
    prospect_icon = find_emoji(interaction, "Prospect")

    async for session in db.get_session():
        member_service = MemberService(session)

        db_member = await member_service.get_member_by_discord_id(member.id)

        if not db_member:
            logger.error(f"Member with d_id {member.id} not found in db")
            return await send_error_response(
                interaction, "Member not found in database."
            )

        embed_description = (
            f"{text_bold(db_member.nickname)} is currently a {prospect_icon} "
            f"{text_bold(ROLE.PROSPECT)} and will become eligible for\nthe "
            f"{eligible_rank_icon} {text_bold(eligible_rank_name)} rank upon "
            f"successful acceptance into the clan\nafter completing the "
            f"{text_bold(f'{PROBATION_DAYS}-day')} probation period."
        )

        target_date = db_member.joined_date + timedelta(days=PROBATION_DAYS)
        remaining_time = target_date - datetime.now(timezone.utc)

        days = max(1, remaining_time.days)
        days_remaining = str(days) + " day"
        days_remaining += "s" if days > 1 else ""

        embed_description += (
            f"\n\n⏳ Approximately {text_bold(days_remaining)} remaining."
        )

        embed = build_response_embed(
            "",
            embed_description,
            discord.Color.from_str("#df781c"),
        )

        await interaction.followup.send(embed=embed)


async def send_member_no_hiscore_values(interaction: discord.Interaction, name: str):
    rank_name = get_rank_from_points(0)
    rank_color = get_rank_color_from_points(0)
    rank_icon = find_emoji(interaction, rank_name)

    embed = build_response_embed(
        f"{rank_icon} {name}",
        (
            "Unable to calculate an accurate score for this member.\n\n"
            "The bot uses the official hiscores to retrieve data about a member. If the account "
            "is new or at a very low level, it may not appear on the hiscores yet. Until an accurate "
            "score can be determined, this member will be assigned the "
            f"{rank_icon} {text_bold(rank_name)} rank.\n\n"
            "-# :information: If your Discord nickname is incorrect please reach out to a member of staff."
        ),
        rank_color,
    )

    await interaction.followup.send(embed=embed)


async def send_not_clan_member(
    interaction: discord.Interaction,
    eligible_rank_name: str,
    eligible_rank_icon: str,
    eligible_rank_color: discord.Color,
    points_total: int,
    name: str,
):
    icon = eligible_rank_icon if points_total > 0 else ":grey_question:"

    description = ""
    if points_total > 0:
        description += (
            "This player is not a member of the clan.\n\n"
            f"If they would join {text_bold('Iron Forged')} they'd be eligible "
            f"for the {eligible_rank_icon} {text_bold(eligible_rank_name)} rank."
        )
    else:
        description += (
            "Unable to calculate an accurate score for this player. Do they exist?\n\n"
            f"{text_sub('...do any of us?')}"
        )

    embed = build_response_embed(
        f"{icon} {name}",
        description,
        eligible_rank_color,
    )

    await interaction.followup.send(embed=embed)
