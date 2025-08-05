import logging
import time

import discord

from ironforgedbot.common.helpers import (
    datetime_to_discord_relative,
    find_emoji,
    format_duration,
    get_discord_role,
)
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import (
    MemberService,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)

logger = logging.getLogger(__name__)


async def _rollback(
    report_channel: discord.TextChannel, discord_member: discord.Member
):
    member_role = get_discord_role(report_channel.guild, ROLE.MEMBER)
    if member_role is None:
        raise ValueError("Unable to access Member role value")

    await discord_member.remove_roles(
        member_role, reason="Error saving member to database"
    )


async def add_member_role(
    report_channel: discord.TextChannel,
    discord_member: discord.Member,
):
    start_time = time.perf_counter()
    rank = get_rank_from_member(discord_member)
    if rank in GOD_ALIGNMENT.list():
        rank = RANK.GOD
    if rank is None:
        rank = RANK.IRON

    async with db.get_session() as session:
        service = MemberService(session)
        reactivate_response = None

        try:
            member = await service.create_member(
                discord_member.id, discord_member.display_name, RANK(rank)
            )
        except (UniqueDiscordIdVolation, UniqueNicknameViolation):
            member = await service.get_member_by_discord_id(discord_member.id)
            if member and not member.active:
                try:
                    reactivate_response = await service.reactivate_member(
                        member.id, discord_member.display_name, RANK(rank)
                    )
                except UniqueNicknameViolation:
                    conflicting_discord_member = report_channel.guild.get_member_named(
                        discord_member.display_name
                    )
                    conflicting_db_member = await service.get_member_by_nickname(
                        discord_member.display_name
                    )
                    conflicting_id = (
                        conflicting_db_member.id if conflicting_db_member else "unknown"
                    )
                    await _rollback(report_channel, discord_member)

                    end_time = time.perf_counter()
                    return await report_channel.send(
                        f":warning: {discord_member.mention} was given the "
                        f"{text_bold(ROLE.MEMBER)} role. But was unable to be saved "
                        f"due to a **nickname conflict**"
                        + (
                            f" with this user: {conflicting_discord_member.mention} "
                            f"\n\n**ID:** {conflicting_id}\n"
                            f"**D_ID:** {conflicting_discord_member.id}"
                            if conflicting_discord_member
                            else "."
                        )
                        + f" Processed in **{format_duration(start_time, end_time)}**.",
                    )
        except Exception as e:
            logger.error(e)
            await _rollback(report_channel, discord_member)

            end_time = time.perf_counter()
            return await report_channel.send(
                f":warning: {discord_member.mention} was given the "
                f"{text_bold(ROLE.MEMBER)} role, but an error occured saving. "
                f"Processed in **{format_duration(start_time, end_time)}**.",
            )

        if not member:
            await _rollback(report_channel, discord_member)

            end_time = time.perf_counter()
            return await report_channel.send(
                f":warning: {discord_member.mention} was given the "
                f"{text_bold(ROLE.MEMBER)} role, but an error occured. "
                f" Processed in **{format_duration(start_time, end_time)}**.",
            )

        if not reactivate_response:
            end_time = time.perf_counter()
            return await report_channel.send(
                f":information: {discord_member.mention} has been given the "
                f"{text_bold(ROLE.MEMBER)} role. Identified as a new member. "
                "Join date set to "
                f"{datetime_to_discord_relative(member.joined_date)}. "
                f"Processed in **{format_duration(start_time, end_time)}**.",
            )

        previous_rank_icon = find_emoji(reactivate_response.previous_rank)
        ingot_icon = find_emoji("Ingot")
        embed = build_response_embed(
            "ℹ️ Previous details",
            "The following are the previous details of this returning member.",
            discord.Color.blue(),
        )
        embed.add_field(name="Nickname", value=reactivate_response.previous_nick)
        embed.add_field(
            name="Joined",
            value=datetime_to_discord_relative(reactivate_response.previous_join_date),
        )
        embed.add_field(
            name="Left",
            value=datetime_to_discord_relative(
                reactivate_response.approximate_leave_date, "R"
            ),
        )
        embed.add_field(
            name="Rank",
            value=f"{previous_rank_icon} {reactivate_response.previous_rank}",
        )
        embed.add_field(
            name="Ingots",
            value=f"{ingot_icon} {reactivate_response.previous_ingot_qty:,}",
        )
        embed.add_field(
            name="Ingots Removed",
            value=("✅ yes" if reactivate_response.ingots_reset else "❌ no"),
        )

        end_time = time.perf_counter()
        return await report_channel.send(
            f":information: {discord_member.mention} has been given the "
            f"{text_bold(ROLE.MEMBER)} role. Identified as a "
            "**returning member**. Join date updated to "
            f"{datetime_to_discord_relative(member.joined_date)}. "
            f"Processed in **{format_duration(start_time, end_time)}**.",
            embed=embed,
        )
