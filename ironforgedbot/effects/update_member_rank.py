import logging
import discord
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.database.database import db

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.services.member_service import MemberService


logger = logging.getLogger(__name__)


async def update_member_rank(
    report_channel: discord.TextChannel, discord_member: discord.Member
):
    if not check_member_has_role(discord_member, ROLE.MEMBER):
        return

    logger.info(f"{discord_member.display_name} has had their rank changed...")
    rank = get_rank_from_member(discord_member)

    if not rank:
        await report_channel.send(
            f"**Error:** Rank changed for {discord_member.mention}, "
            f"but rank could not be determined."
        )
        return

    if rank in GOD_ALIGNMENT.list():
        rank = RANK.GOD

    async with db.get_session() as session:
        service = MemberService(session)
        member = await service.get_member_by_discord_id(discord_member.id)

        if not member:
            await report_channel.send(
                f"**Error:** Rank role changed for {discord_member.mention}, "
                f"but database member not found. Rank: {rank}."
            )
            return

        if member.rank != rank:
            await service.change_rank(member.id, RANK(rank))
            rank_emoji = find_emoji(rank)
            await report_channel.send(
                f"**ℹ️ Rank changed:** {discord_member.mention}'s rank was changed to "
                f"{rank_emoji} **{RANK(rank)}**. Database updated."
            )
