import logging
import discord
import time

from discord.errors import Forbidden
from ironforgedbot.common.helpers import format_duration, get_discord_role
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_ul


logger = logging.getLogger(__name__)


async def add_banned_role(report_channel: discord.TextChannel, member: discord.Member):
    # short circuit for now while discussing improved strategy
    return
    start_time = time.perf_counter()
    roles_to_remove = set(role.name for role in member.roles)
    member_roles = RANK.list() + ROLE.list() + GOD_ALIGNMENT.list()
    roles_to_remove = set(roles_to_remove) - set(member_roles)

    roles_removed = []
    for role_name in roles_to_remove:
        role = get_discord_role(report_channel.guild, role_name)

        if role_name == "@everyone":
            continue

        if not role:
            logger.error(f"Unknown role: {role_name}")
            raise ValueError(f"Unable to get role {role_name}")

        roles_removed.append(role)

    try:
        await member.remove_roles(*roles_removed, reason="Member banned.")
    except Forbidden:
        logger.error(f"Forbidden from modifying {member.display_name}'s roles")
        return await report_channel.send(
            f":warning: The bot lacks permission to manage {member.mention}'s roles."
        )
    except Exception as e:
        logger.error(
            f"Exception when modifying {member.display_name}'s roles\n{roles_removed}"
        )
        return await report_channel.send(
            f":warning: Something went wrong trying to remove a role.\n{e}"
        )

    end_time = time.perf_counter()
    await report_channel.send(
        f":x: **Member banned:** {member.mention} has been banned. "
        "Removed the following unmonitored **discord roles** "
        f"from this user:\n{text_ul([r.name for r in roles_removed])}"
        f"Processed in **{format_duration(start_time, end_time)}**.",
    )

    member_role = get_discord_role(report_channel.guild, ROLE.MEMBER)
    if member_role:
        await report_channel.send(f"Now removing {member.mention}'s **MEMBER** role...")
        await member.remove_roles(member_role, reason="Member banned.")
