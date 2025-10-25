from datetime import datetime, timedelta, timezone
import io
import logging
import os
import discord

from ironforgedbot.common.helpers import find_emoji, get_text_channel
from ironforgedbot.common.ranks import get_rank_color_from_points, get_rank_from_points
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold, text_sub
from ironforgedbot.config import CONFIG
from ironforgedbot.logging_config import get_logger_instance
from ironforgedbot.services.service_factory import create_member_service
from ironforgedbot.tasks.job_refresh_ranks import PROBATION_DAYS
from ironforgedbot.database.database import db

logger = logging.getLogger(__name__)


async def send_error_response(
    interaction: discord.Interaction, message: str, report_to_channel: bool = True
):
    """Send an error response embed to the user via followup."""
    embed = discord.Embed(
        title=":exclamation: Error", description=message, color=discord.Colour.red()
    )

    await interaction.followup.send(embed=embed)

    if report_to_channel:
        await _send_error_report(interaction, message)


async def send_ephemeral_error(interaction: discord.Interaction, message: str):
    """Send an ephemeral error message, cleaning up any public defer if needed.

    If the interaction has been deferred publicly, this will delete the
    "Bot is thinking..." message and send an ephemeral followup instead.
    """
    embed = discord.Embed(
        title=":exclamation: Error", description=message, color=discord.Colour.red()
    )

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        try:
            await interaction.delete_original_response()
        except Exception:
            pass  # Ignore if already deleted or doesn't exist

        await interaction.followup.send(embed=embed, ephemeral=True)


async def _send_error_report(interaction: discord.Interaction, error_message: str):
    """Send error report to admin channel with debug information."""
    try:
        report_channel = get_text_channel(
            interaction.guild, CONFIG.AUTOMATION_CHANNEL_ID
        )
        if not report_channel:
            logger.warning("Unable to find report channel for error reporting")
            return

        command_name = (
            interaction.command.name if interaction.command else "Unknown Command"
        )
        channel_mention = (
            interaction.channel.mention if interaction.channel else "Unknown Channel"
        )

        message_link = f"https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}"

        try:
            guild_member = interaction.guild.get_member(interaction.user.id)
            if guild_member and check_member_has_role(guild_member, ROLE.LEADERSHIP):
                user_role = "Leadership"
            elif guild_member and check_member_has_role(guild_member, ROLE.MEMBER):
                user_role = "Member"
            else:
                user_role = "Guest/Other"
        except Exception:
            user_role = "Unknown"

        error_embed = build_response_embed(
            title="🚨 Command Error Report",
            description=f"An error occurred while processing a command.",
            color=discord.Colour.red(),
        )

        error_embed.add_field(
            name="User",
            value=f"{interaction.user.mention} `{interaction.user.id}`",
            inline=True,
        )

        error_embed.add_field(name="Role", value=user_role, inline=True)

        error_embed.add_field(
            name="Command",
            value=f"`/{command_name}` in {channel_mention} [[GO]]({message_link})",
            inline=False,
        )

        try:
            parameters = []
            if interaction.data and "options" in interaction.data:
                for option in interaction.data["options"]:
                    param_name = option.get("name", "unknown")
                    param_value = option.get("value", "N/A")
                    parameters.append(f"• `{param_name}`: {param_value}")

            if parameters:
                param_text = "\n".join(parameters)
                if len(param_text) > 800:  # Truncate if too long
                    param_text = param_text[:800] + "..."
            else:
                param_text = "No parameters"
        except Exception:
            param_text = "Unable to extract parameters"

        error_embed.add_field(
            name="Parameters",
            value=param_text,
            inline=False,
        )

        utc_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        error_embed.add_field(
            name="Timestamp",
            value=f"`{utc_timestamp}`",
            inline=False,
        )

        error_embed.add_field(
            name="Error Message",
            value=f"```{error_message[:1000]}{'...' if len(error_message) > 1000 else ''}```",
            inline=False,
        )

        log_file = _get_latest_log_lines_file()
        if log_file:
            await report_channel.send(embed=error_embed, file=log_file)
        else:
            await report_channel.send(embed=error_embed)

    except Exception as e:
        # Don't let error reporting failure break the main functionality
        logger.error(f"Failed to send error report: {e}")


def _get_latest_log_lines_file(line_count: int = 50) -> discord.File | None:
    """Extract the latest N lines from the log file and return as Discord file.

    Args:
        line_count: Number of lines to extract from the end of the log file

    Returns:
        Discord File object with log lines, or None if unavailable
    """
    try:
        # Find all log files in the log directory
        log_dir = get_logger_instance().log_dir
        files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        files = [f for f in files if os.path.isfile(f) and f.endswith(".log")]

        if not files:
            logger.warning("No log files found for error report attachment")
            return None

        # Get the most recent log file
        latest_file = max(files, key=os.path.getmtime)

        # Read the last N lines efficiently
        lines = []
        with open(latest_file, "r", encoding="utf-8") as file:
            # Read all lines and get the last N
            all_lines = file.readlines()
            lines = all_lines[-line_count:]

        if not lines:
            logger.warning("No log lines found in latest log file")
            return None

        # Create file content preserving original formatting
        log_content = "".join(lines)

        # Create filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"error_log_context_{timestamp}.txt"

        # Create Discord file from string content
        file_data = io.StringIO(log_content)
        return discord.File(file_data, filename=filename)

    except FileNotFoundError:
        logger.warning("Log directory not found for error report attachment")
        return None
    except PermissionError:
        logger.warning("Permission denied accessing log files for error report")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error creating log attachment: {e}")
        return None


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
    prospect_icon = find_emoji("Prospect")

    async with db.get_session() as session:
        member_service = create_member_service(session)

        db_member = await member_service.get_member_by_discord_id(member.id)

        if not db_member:
            logger.error(f"Member with d_id {member.id} not found in db")
            return await send_error_response(
                interaction, "Member not found in database."
            )

        embed_description = (
            f"{text_bold(db_member.nickname)} is currently a {prospect_icon} "
            f"{text_bold(ROLE.PROSPECT)} and will become eligible for the "
            f"{eligible_rank_icon} {text_bold(eligible_rank_name)} rank upon "
            f"successful acceptance into the clan after completing the "
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
    rank_icon = find_emoji(rank_name)

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
