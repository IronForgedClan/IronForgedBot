import logging

import discord

from ironforgedbot.common.helpers import (
    normalize_discord_string,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import Member, StorageError

logger = logging.getLogger(__name__)


async def sync_members(guild: discord.Guild) -> list[str]:
    # Perform a cross join between current Discord members and
    # entries in the sheet.
    # First, read all members from Discord.
    output = []
    members = []
    member_ids = []

    for member in guild.members:
        if check_member_has_role(member, ROLE.MEMBER):
            members.append(member)
            member_ids.append(member.id)

    # Then, get all current entries from storage.
    try:
        existing = await STORAGE.read_members()
    except StorageError as error:
        logger.error(f"Encountered error reading members: {error}")
        raise

    written_ids = [member.id for member in existing]

    # Now for the actual diffing.
    # First, what new members are in Discord but not the sheet?
    new_members = []
    for member in members:
        if member.id not in written_ids:
            # Don't allow users without a nickname into storage.
            if not member.nick or len(member.nick) < 1:
                output.append(
                    f"skipped user {member.name} because they don't have a nickname in Discord"
                )
                continue
            new_members.append(
                Member(
                    id=int(member.id),
                    runescape_name=normalize_discord_string(member.nick).lower(),
                    ingots=0,
                )
            )
            output.append(
                f"added user {normalize_discord_string(member.nick).lower()} because they joined"
            )

    if len(new_members) > 0:
        try:
            await STORAGE.add_members(new_members, "User Joined Server")
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
    for member in members:
        for existing_member in existing:
            if member.id == existing_member.id:
                # If a member is already in storage but had their nickname
                # unset, set rsn to their Discord name.
                # Otherwise, sorting fails when comparing NoneType.
                if member.nick is None:
                    if member.name != existing_member.runescape_name:
                        changed_members.append(
                            Member(
                                id=existing_member.id,
                                runescape_name=normalize_discord_string(
                                    member.name
                                ).lower(),
                                ingots=existing_member.ingots,
                                joined_date=str(existing_member.joined_date),
                            )
                        )
                else:
                    if (
                        normalize_discord_string(member.nick).lower()
                        != existing_member.runescape_name
                    ):
                        changed_members.append(
                            Member(
                                id=existing_member.id,
                                runescape_name=normalize_discord_string(
                                    member.nick
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
