import logging
from typing import Dict

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.common.roles import (
    ROLE,
    check_member_has_role,
    get_highest_privilage_role_from_member,
)
from ironforgedbot.database.database import db
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    MemberService,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)

logger = logging.getLogger(__name__)


async def sync_members(guild: discord.Guild) -> list[list]:
    """Sync Discord members with database, returning list of changes."""
    discord_members: Dict[int, discord.Member] = {}
    for discord_member in guild.members:
        if check_member_has_role(discord_member, ROLE.MEMBER):
            discord_members[discord_member.id] = discord_member

    output = []
    async with db.get_session() as session:
        service = MemberService(session)
        db_members = await service.get_all_active_members()

        existing_members: Dict[int, Member] = {}
        for member in db_members:
            existing_members[member.discord_id] = member

        # disable members in db if no longer in Discord
        for member in existing_members.values():
            if member.discord_id not in discord_members.keys():
                await service.disable_member(member.id)
                output.append([member.nickname, "Disabled", "No longer a member"])

        # update nickname and rank
        for discord_member in discord_members.values():
            for member in existing_members.values():
                if discord_member.id == member.discord_id:
                    change_text = ""
                    safe_nick = normalize_discord_string(discord_member.nick or "")

                    if safe_nick != member.nickname:
                        try:
                            await service.change_nickname(member.id, safe_nick)
                        except UniqueNicknameViolation:
                            output.append(
                                [
                                    discord_member.name,
                                    "Error",
                                    "Unique nickname violation",
                                ]
                            )
                            continue
                        change_text += "Nickname changed "

                    discord_rank = get_rank_from_member(discord_member)
                    if discord_rank in GOD_ALIGNMENT.list():
                        discord_rank = RANK.GOD

                    if discord_rank:
                        if member.rank != discord_rank:
                            await service.change_rank(member.id, RANK(discord_rank))
                            change_text += "Rank changed"

                    discord_role = get_highest_privilage_role_from_member(
                        discord_member
                    )
                    if discord_role:
                        if member.role != discord_role:
                            await service.change_role(
                                member.id, ROLE(discord_role), admin_id=None
                            )
                            change_text += " Role changed"

                    if len(change_text) > 0:
                        output.append([safe_nick, "Updated", change_text])

        # add new members or reactivate returning members
        for discord_member in discord_members.values():
            if discord_member.id not in existing_members.keys():
                safe_nick = normalize_discord_string(discord_member.nick or "")
                rank = get_rank_from_member(discord_member)
                if rank in GOD_ALIGNMENT.list():
                    rank = RANK.GOD

                if not rank:
                    rank = RANK.IRON

                if not discord_member.nick or len(safe_nick) < 1:
                    output.append([safe_nick, "Error", "No nickname"])
                    continue

                try:
                    await service.create_member(
                        discord_member.id, safe_nick, RANK(rank)
                    )
                except (UniqueDiscordIdVolation, UniqueNicknameViolation):
                    disabled_member = await service.get_member_by_discord_id(
                        discord_member.id
                    )
                    if disabled_member and not disabled_member.active:
                        try:
                            await service.reactivate_member(
                                disabled_member.id, safe_nick, RANK(rank)
                            )
                        except UniqueNicknameViolation:
                            output.append(
                                [
                                    f"[D]{discord_member.name}",
                                    "Error",
                                    "Nickname dupe",
                                ]
                            )
                            continue

                        output.append([safe_nick, "Enabled", "Returning member"])
                        continue
                    else:
                        output.append([safe_nick, "Error", "Data continuity error"])
                except Exception as e:
                    logger.error(f"Unexpected error creating member {safe_nick}: {e}")
                    output.append([safe_nick, "Error", "Uncaught exception"])
                    continue

                output.append([safe_nick, "Added", "New member created"])

        output = sorted(output, key=lambda x: x[0])
    return output


@log_command_execution(logger)
async def cmd_sync_members(
    interaction: discord.Interaction, report_channel: discord.TextChannel
):
    """Execute member sync job manually."""
    assert interaction.guild

    await interaction.response.send_message(
        "## Manually initiating member sync job...\n"
        f"View <#{report_channel.id}> for output.",
        ephemeral=True,
    )

    # Import here to avoid circular import
    from ironforgedbot.tasks.job_sync_members import job_sync_members

    await job_sync_members(interaction.guild, report_channel)
