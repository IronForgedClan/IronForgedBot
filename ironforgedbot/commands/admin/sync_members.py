import logging
import sqlite3
from typing import Dict
import discord

from ironforgedbot.common.helpers import (
    normalize_discord_string,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.services.member_service import (
    MemberService,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import Member, StorageError
from ironforgedbot.database.database import db

logger = logging.getLogger(__name__)


async def sync_members(guild: discord.Guild) -> list[tuple[str, str]]:
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

        created_members = []
        for _, discord_member in discord_members.items():
            if discord_member.id not in existing_members:
                safe_nick = normalize_discord_string(discord_member.nick or "")
                if not discord_member.nick or len(safe_nick) < 1:
                    created_members.append(
                        (
                            normalize_discord_string(discord_member.display_name),
                            "Error NONICK",
                        )
                    )
                    continue

                try:
                    await service.create_member(discord_member.id, safe_nick)
                except UniqueDiscordIdVolation:
                    created_members.append((safe_nick, "Error UDID"))
                    continue
                except UniqueNicknameViolation:
                    created_members.append((safe_nick, "Error UNICK"))
                    continue

                created_members.append((safe_nick, "Added"))

        removed_members = []
        # for db_member in existing_members:
        #     if db_member.id not in discord_members:
        #         remove_members.append(db_member)
        #         await service.change_activity(db_member.id, False)

        updated_members = []
        # for discord_member in discord_members:
        #     for db_member in existing_members:
        #         if discord_member.id == db_member.discord_id:
        #             if discord_member.nick != db_member.nickname:
        #                 update_members.append(discord_member)
        #                 await service.change_nickname(db_member.id, discord_member.nick)

        output = sorted(
            created_members + updated_members + removed_members, key=lambda x: x[0]
        )
    print("-------------")
    print(output)
    return output

    # Perform a cross join between current Discord members and
    # entries in the sheet.
    # First, read all members from Discord.
    output = []
    members = []
    member_ids = []

    for discord_member in guild.members:
        if check_member_has_role(discord_member, ROLE.MEMBER):
            members.append(discord_member)
            member_ids.append(discord_member.id)

    # Then, get all current entries from storage.
    try:
        existing = await STORAGE.read_members()
    except StorageError as error:
        logger.error(f"Encountered error reading members: {error}")
        raise

    written_ids = [discord_member.id for discord_member in existing]

    # Now for the actual diffing.
    # First, what new members are in Discord but not the sheet?
    created_members = []
    for discord_member in members:
        if discord_member.id not in written_ids:
            # Don't allow users without a nickname into storage.
            if not discord_member.nick or len(discord_member.nick) < 1:
                output.append(
                    f"skipped user {discord_member.name} because they don't have a nickname in Discord"
                )
                continue
            created_members.append(
                Member(
                    id=int(discord_member.id),
                    runescape_name=normalize_discord_string(
                        discord_member.nick
                    ).lower(),
                    ingots=0,
                )
            )
            output.append(
                f"added user {normalize_discord_string(discord_member.nick).lower()} because they joined"
            )

    if len(created_members) > 0:
        try:
            await STORAGE.add_members(created_members, "User Joined Server")
        except StorageError as error:
            logger.error(f"Encountered error writing new members: {error}")
            raise

    # Okay, now for all the users who have left.
    leaving_members = []
    for existing_member in existing:
        if existing_member.id not in member_ids:
            leaving_members.append(existing_member)
            output.append(
                f"removed user {existing_member.runescape_name} because they left the server"
            )

    if len(leaving_members) > 0:
        try:
            await STORAGE.remove_members(leaving_members, "User Left Server")
        except StorageError as error:
            logger.error(f"Encountered error removing members: {error}")
            raise

    # Update all users that have changed their RSN.
    changed_members = []
    for discord_member in members:
        for existing_member in existing:
            if discord_member.id == existing_member.id:
                # If a member is already in storage but had their nickname
                # unset, set rsn to their Discord name.
                # Otherwise, sorting fails when comparing NoneType.
                if discord_member.nick is None:
                    if discord_member.name != existing_member.runescape_name:
                        changed_members.append(
                            Member(
                                id=existing_member.id,
                                runescape_name=normalize_discord_string(
                                    discord_member.name
                                ).lower(),
                                ingots=existing_member.ingots,
                                joined_date=str(existing_member.joined_date),
                            )
                        )
                else:
                    if (
                        normalize_discord_string(discord_member.nick).lower()
                        != existing_member.runescape_name
                    ):
                        changed_members.append(
                            Member(
                                id=existing_member.id,
                                runescape_name=normalize_discord_string(
                                    discord_member.nick
                                ).lower(),
                                ingots=existing_member.ingots,
                                joined_date=str(existing_member.joined_date),
                            )
                        )

    if len(changed_members) > 0:
        for changed_member in changed_members:
            output.append(f"updated RSN for {changed_member.runescape_name}")

        try:
            await STORAGE.update_members(changed_members, "Name Change")
        except StorageError as error:
            logger.error(f"Encountered error updating changed members: {error}")
            raise

    return output
