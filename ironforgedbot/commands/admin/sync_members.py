import logging
from types import SimpleNamespace
from typing import Dict

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK, get_rank_from_member
from ironforgedbot.common.roles import (
    ROLE,
    check_member_has_role,
    get_highest_privilage_role_from_member,
    get_member_flags_from_discord,
    get_flag_changes,
)
from ironforgedbot.database.database import db
from ironforgedbot.services.member_service import (
    MemberService,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)

logger = logging.getLogger(__name__)


async def sync_members(guild: discord.Guild) -> list[list]:
    """Sync Discord members with database, returning list of changes."""
    output = []

    # Grab a list of all Discord members with the Member role
    discord_members: Dict[int, discord.Member] = {}
    for discord_member in guild.members:
        if check_member_has_role(discord_member, ROLE.MEMBER):
            discord_members[discord_member.id] = discord_member

    async with db.get_session() as session:
        service = MemberService(session)

        # All database reads must happen before any commits
        # SQLAlchemy expires ORM object attributes after each commit
        # Raises MissingGreenlet if an expired attribute is accessed
        db_members = await service.get_all_active_members()
        db_inactive_members = await service.get_all_inactive_members()

        existing_members: Dict[int, SimpleNamespace] = {
            m.discord_id: SimpleNamespace(
                id=m.id,
                discord_id=m.discord_id,
                nickname=m.nickname,
                rank=m.rank,
                role=m.role,
                is_booster=m.is_booster,
                is_prospect=m.is_prospect,
                is_blacklisted=m.is_blacklisted,
                is_banned=m.is_banned,
            )
            for m in db_members
        }

        # Inactive members are only synced for flag changes
        inactive_members: list[SimpleNamespace] = [
            SimpleNamespace(
                id=m.id,
                discord_id=m.discord_id,
                nickname=m.nickname,
                is_booster=m.is_booster,
                is_prospect=m.is_prospect,
                is_blacklisted=m.is_blacklisted,
                is_banned=m.is_banned,
            )
            for m in db_inactive_members
        ]

        # Disable members if no longer in Discord
        for discord_id, member in existing_members.items():
            if discord_id not in discord_members:
                await service.disable_member(member.id)
                output.append([member.nickname, "Disabled", "No longer a member"])

        # Update existing members
        for discord_member in discord_members.values():
            member = existing_members.get(discord_member.id)

            if member is not None:
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

                discord_role = get_highest_privilage_role_from_member(discord_member)
                if discord_role:
                    if member.role != discord_role:
                        await service.change_role(
                            member.id, ROLE(discord_role), admin_id=None
                        )
                        change_text += " Role changed"

                discord_flags = get_member_flags_from_discord(discord_member)
                flag_changes = get_flag_changes(member, discord_flags)
                if flag_changes:
                    await service.update_member_flags(member.id, **discord_flags)
                    change_text += " Flags: " + ", ".join(flag_changes)

                if len(change_text) > 0:
                    output.append([safe_nick, "Updated", change_text])

            else:
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
                    new_member = await service.create_member(
                        discord_member.id, safe_nick, RANK(rank)
                    )
                    await service.update_member_flags(
                        new_member.id, **get_member_flags_from_discord(discord_member)
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

                        await service.update_member_flags(
                            disabled_member.id,
                            **get_member_flags_from_discord(discord_member),
                        )

                        output.append([safe_nick, "Enabled", "Returning member"])
                        continue
                    else:
                        output.append([safe_nick, "Error", "Data continuity error"])
                except Exception as e:
                    logger.error(f"Unexpected error creating member {safe_nick}: {e}")
                    output.append([safe_nick, "Error", "Uncaught exception"])
                    continue

                output.append([safe_nick, "Added", "New member created"])

        # Sync flags for inactive members still in the Discord server
        for member in inactive_members:
            discord_member = guild.get_member(member.discord_id)
            if not discord_member:
                continue

            discord_flags = get_member_flags_from_discord(discord_member)
            flag_changes = get_flag_changes(member, discord_flags)
            if flag_changes:
                await service.update_member_flags(member.id, **discord_flags)
                output.append(
                    [member.nickname, "Inactive Updated", ", ".join(flag_changes)]
                )

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
