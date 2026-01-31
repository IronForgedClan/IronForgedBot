import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

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
from ironforgedbot.events.handlers.base import BaseMemberUpdateHandler
from ironforgedbot.events.member_events import MemberUpdateContext
from ironforgedbot.events.member_update_emitter import member_update_emitter
from ironforgedbot.services.member_service import MemberService, UniqueNicknameViolation

import discord
import time

logger = logging.getLogger(__name__)


class AddMemberRoleHandler(BaseMemberUpdateHandler):
    """Handler for when the Member role is added to a Discord user.

    Creates a new member record or reactivates an existing inactive member.
    Runs early (priority 10) since other handlers may depend on the member existing.
    """

    priority = 10

    @property
    def name(self) -> str:
        return "AddMemberRole"

    def should_handle(self, context: MemberUpdateContext) -> bool:
        return ROLE.MEMBER in context.roles_added

    async def _rollback(self, context: MemberUpdateContext) -> None:
        """Remove the Member role if database operation fails."""
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
        start_time = time.perf_counter()
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
                    return await self._handle_nickname_conflict(
                        context, service, start_time
                    )
            elif existing_member and existing_member.active:
                logger.warning(
                    f"Member {discord_member.display_name} (ID: {discord_member.id}) "
                    "already exists and is active in database"
                )
                await self._rollback(context)
                end_time = time.perf_counter()
                return (
                    f":warning: {discord_member.mention} was given the "
                    f"{text_bold(ROLE.MEMBER)} role, but they are already registered "
                    f"as an active member. Processed in **{format_duration(start_time, end_time)}**."
                )
            else:
                member = await service.create_member(
                    discord_member.id, discord_member.display_name, RANK(rank)
                )
        except UniqueNicknameViolation:
            return await self._handle_nickname_conflict(context, service, start_time)

        if not member:
            await self._rollback(context)
            end_time = time.perf_counter()
            return (
                f":warning: {discord_member.mention} was given the "
                f"{text_bold(ROLE.MEMBER)} role, but an error occured. "
                f"Processed in **{format_duration(start_time, end_time)}**."
            )

        if not reactivate_response:
            end_time = time.perf_counter()
            return (
                f":information: {discord_member.mention} has been given the "
                f"{text_bold(ROLE.MEMBER)} role. Identified as a new member. "
                f"Join date set to {datetime_to_discord_relative(member.joined_date)}. "
                f"Processed in **{format_duration(start_time, end_time)}**."
            )

        # Returning member - send detailed embed
        previous_rank_icon = find_emoji(reactivate_response.previous_rank)
        ingot_icon = find_emoji("Ingot")
        embed = build_response_embed(
            "ℹ️ Returning Member",
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
            value=("Yes" if reactivate_response.ingots_reset else "No"),
        )

        end_time = time.perf_counter()
        await context.report_channel.send(
            f":information: {discord_member.mention} has been given the "
            f"{text_bold(ROLE.MEMBER)} role. Identified as a "
            f"**returning member**. Join date updated to "
            f"{datetime_to_discord_relative(member.joined_date)}. "
            f"Processed in **{format_duration(start_time, end_time)}**.",
            embed=embed,
        )
        return None  # Already sent message with embed

    async def _handle_nickname_conflict(
        self,
        context: MemberUpdateContext,
        service: MemberService,
        start_time: float,
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

        end_time = time.perf_counter()
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
            f"due to a **nickname conflict**{conflict_info} "
            f"Processed in **{format_duration(start_time, end_time)}**."
        )


member_update_emitter.register(AddMemberRoleHandler())
