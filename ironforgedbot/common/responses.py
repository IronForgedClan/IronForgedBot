from datetime import datetime, timedelta, timezone
import logging
import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.storage.types import StorageError

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
    from ironforgedbot.storage.sheets import STORAGE
    from ironforgedbot.tasks.job_refresh_ranks import PROBATION_DAYS

    prospect_icon = find_emoji(interaction, "Prospect")
    storage_member = None

    try:
        storage_member = await STORAGE.read_member(member.display_name)
    except StorageError as e:
        logger.error(e)

    embed_description = (
        f"{text_bold(member.display_name)} is currently a {prospect_icon} {text_bold(ROLE.PROSPECT)} and "
        f"will become eligible for the {eligible_rank_icon} {text_bold(eligible_rank_name)} rank upon "
        f"successful acceptance into the clan after completing the {text_bold(f"{PROBATION_DAYS}-day")} "
        "probation period."
    )

    if storage_member and isinstance(storage_member.joined_date, datetime):
        target_date = storage_member.joined_date + timedelta(days=PROBATION_DAYS)
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
