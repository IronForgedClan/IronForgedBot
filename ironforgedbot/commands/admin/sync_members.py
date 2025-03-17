import logging
from typing import Dict

import discord

from ironforgedbot.common.helpers import (
    normalize_discord_string,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.database.database import db
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    MemberService,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)

logger = logging.getLogger(__name__)


async def sync_members(guild: discord.Guild) -> list[list]:
    discord_members: Dict[int, discord.Member] = {}
    for discord_member in guild.members:
        if check_member_has_role(discord_member, ROLE.MEMBER):
            discord_members[discord_member.id] = discord_member

    output = []
    async for session in db.get_session():
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

        # update nicknames
        for discord_member in discord_members.values():
            for member in existing_members.values():
                if discord_member.id == member.discord_id:
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
                        output.append([safe_nick, "Updated", "Nickname changed"])

        # add new members or reactivate returning members
        for discord_member in discord_members.values():
            if discord_member.id not in existing_members.keys():
                safe_nick = normalize_discord_string(discord_member.nick or "")
                if not discord_member.nick or len(safe_nick) < 1:
                    output.append([safe_nick, "Error", "No nickname"])
                    continue

                try:
                    await service.create_member(discord_member.id, safe_nick)
                except (UniqueDiscordIdVolation, UniqueNicknameViolation):
                    disabled_member = await service.get_member_by_discord_id(
                        discord_member.id
                    )
                    if disabled_member and not disabled_member.active:
                        try:
                            await service.reactivate_member(
                                disabled_member.id, safe_nick
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
                except Exception as e:
                    logger.error(e)
                    output.append([safe_nick, "Error", "Uncaught exception"])
                    continue

                output.append([safe_nick, "Added", "New member created"])

        output = sorted(output, key=lambda x: x[0])
    return output
