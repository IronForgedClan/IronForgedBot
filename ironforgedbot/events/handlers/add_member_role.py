import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import (
    datetime_to_discord_relative,
    find_emoji,
    get_discord_role,
)
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService, UniqueNicknameViolation

import discord

logger = logging.getLogger(__name__)


class AddMemberRoleHandler(BaseMemberUpdateHandler):
    priority = 10

    @property
    def name(self) -> str:
        return "AddMemberRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return ROLE.MEMBER in context.roles_added

    async def _rollback(self, context: MemberUpdateContext) -> None:
        member_role = get_discord_role(context.report_channel.guild, ROLE.MEMBER)
        if member_role:
            await context.after.remove_roles(
                member_role, reason="Error saving member to database"
            )
            member_update_emitter.suppress_next_for(context.discord_id)

    async def _on_error(
        self, context: MemberUpdateContext, error: Exception
    ) -> Optional[str]:
        await self._rollback(context)
        return await super()._on_error(context, error)

    async def _execute(
        self,
        context: MemberUpdateContext,
        session: AsyncSession,
        service: MemberService,
    ) -> Optional[str]:
        discord_member = context.after

        rank = get_rank_from_member(discord_member)
        if rank in GOD_ALIGNMENT.list():
            rank = RANK.GOD
        if rank is None:
            rank = RANK.IRON

        reactivate_response = None

        try:
            existing_member = await service.get_member_by_discord_id(discord_member.id)

            if existing_member and not existing_member.active:
                try:
                    reactivate_response = await service.reactivate_member(
                        existing_member.id, discord_member.display_name, RANK(rank)
                    )
                    member = reactivate_response.new_member
                except UniqueNicknameViolation:
                    return await self._handle_nickname_conflict(context, service)
            elif existing_member and existing_member.active:
                logger.warning(
                    f"Member {discord_member.display_name} (ID: {discord_member.id}) "
                    "already exists and is active in database"
                )
                await self._rollback(context)
                return (
                    f":warning: {discord_member.mention} was given the "
                    f"{text_bold(ROLE.MEMBER)} role, but they are already registered "
                    "as an active member."
                )
            else:
                member = await service.create_member(
                    discord_member.id, discord_member.display_name, RANK(rank)
                )
        except UniqueNicknameViolation:
            return await self._handle_nickname_conflict(context, service)

        if not member:
            await self._rollback(context)
            return (
                f":warning: {discord_member.mention} was given the "
                f"{text_bold(ROLE.MEMBER)} role, but an error occured."
            )

        if not reactivate_response:
            return (
                f":information: {discord_member.mention} has been given the "
                f"{text_bold(ROLE.MEMBER)} role. Identified as a new member. "
                f"Join date changed to {datetime_to_discord_relative(member.joined_date)}. "
            )

        previous_rank_icon = find_emoji(reactivate_response.previous_rank)
        ingot_icon = find_emoji("Ingot")
        embed = build_response_embed(
            "ℹ️ Returning Member",
            "The previous details of the returning member.",
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
            value=("Yes" if reactivate_response.ingots_reset else "No"),
        )

        await context.report_channel.send(
            f":information: {discord_member.mention} has been given the "
            f"{text_bold(ROLE.MEMBER)} role. Identified as a "
            f"**returning member**. Join date changed to "
            f"{datetime_to_discord_relative(member.joined_date)}.",
            embed=embed,
        )
        return None

    async def _handle_nickname_conflict(
        self,
        context: MemberUpdateContext,
        service: MemberService,
    ) -> str:
        discord_member = context.after
        conflicting_discord_member = context.report_channel.guild.get_member_named(
            discord_member.display_name
        )
        conflicting_db_member = await service.get_member_by_nickname(
            discord_member.display_name
        )
        conflicting_id = (
            conflicting_db_member.id if conflicting_db_member else "unknown"
        )
        await self._rollback(context)

        conflict_info = ""
        if conflicting_discord_member:
            conflict_info = (
                f" with this user: {conflicting_discord_member.mention} "
                f"\n\n**ID:** {conflicting_id}\n"
                f"**D_ID:** {conflicting_discord_member.id}"
            )
        else:
            conflict_info = "."

        return (
            f":warning: {discord_member.mention} was given the "
            f"{text_bold(ROLE.MEMBER)} role. But was unable to be saved "
            f"due to a **nickname conflict**{conflict_info}."
        )


member_update_emitter.register(AddMemberRoleHandler())
