import logging
import discord

from ironforgedbot.common.helpers import datetime_to_discord_relative, find_emoji
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.services.member_service import (
    MemberService,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)
from ironforgedbot.database.database import db

logger = logging.getLogger(__name__)


async def add_member_role(
    report_channel: discord.TextChannel,
    discord_member: discord.Member,
):
    rank = get_rank_from_member(discord_member)
    if rank in GOD_ALIGNMENT.list():
        rank = RANK.GOD
    if rank is None:
        rank = RANK.IRON

    async for session in db.get_session():
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
                    conflict_discord_member = report_channel.guild.get_member_named(
                        discord_member.display_name
                    )
                    await report_channel.send(
                        f":error: {discord_member.mention} was given the "
                        f"{text_bold(ROLE.MEMBER)} role, but has a duplicate "
                        "nickname and cannot be saved. "
                        + (
                            "In conflict with this user: "
                            f"{conflict_discord_member.mention}"
                            if conflict_discord_member
                            else ""
                        )
                    )
                    continue
        except Exception as e:
            logger.error(e)
            await report_channel.send(
                f":warning: {discord_member.mention} was given the "
                f"{text_bold(ROLE.MEMBER)} role, but an error occured saving."
            )
            continue

        if member:
            if reactivate_response:
                rank_icon = find_emoji(reactivate_response.previous_rank)
                ingot_icon = find_emoji("Ingot")
                embed = build_response_embed(
                    "ℹ️ Previous details",
                    "The following are the previous details of this returning member.",
                    discord.Color.blue(),
                )
                embed.add_field(
                    name="Nickname", value=reactivate_response.previous_nick
                )
                embed.add_field(
                    name="Joined",
                    value=datetime_to_discord_relative(
                        reactivate_response.previous_join_date
                    ),
                )
                embed.add_field(
                    name="Left",
                    value=datetime_to_discord_relative(
                        reactivate_response.approximate_leave_date, "R"
                    ),
                )
                embed.add_field(
                    name="Rank",
                    value=f"{rank_icon} {reactivate_response.previous_rank}",
                )
                embed.add_field(
                    name="Ingots",
                    value=f"{ingot_icon} {reactivate_response.previous_ingot_qty:,}",
                )
                embed.add_field(
                    name="Ingots Reset",
                    value=("✅" if reactivate_response.ingots_reset else "❌"),
                )

                return await report_channel.send(
                    f":information: {discord_member.mention} has been given the "
                    f"{text_bold(ROLE.MEMBER)} role. Identified as a "
                    "**returning member**. Join date updated to "
                    f"{datetime_to_discord_relative(member.joined_date)}.\n",
                    embed=embed,
                )
            return await report_channel.send(
                f":information: {discord_member.mention} has been given the "
                f"{text_bold(ROLE.MEMBER)} role. Identified as a new member. "
                "Join date set to "
                f"{datetime_to_discord_relative(member.joined_date)}.\n",
            )
        else:
            return await report_channel.send(
                f":warning: {discord_member.mention} was given the "
                f"{text_bold(ROLE.MEMBER)} role, but an error occured."
            )
