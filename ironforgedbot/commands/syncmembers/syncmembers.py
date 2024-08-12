import logging

import discord

from ironforgedbot.commands import protected_command
from ironforgedbot.common.helpers import validate_member_has_role, normalize_discord_string, \
    fit_log_lines_into_discord_messages
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import IngotsStorage, StorageError, Member

logger = logging.getLogger(__name__)


@protected_command(role=ROLES.LEADERSHIP)
async def cmd_sync_members(interaction: discord.Interaction, guild: discord.Guild, storage: IngotsStorage):
    try:
        lines = sync_members(guild, storage)
    except StorageError as error:
        await send_error_response(interaction, f"Encountered error syncing members: {error}")
        return

    discord_messages = fit_log_lines_into_discord_messages(lines)
    if 0 == len(discord_messages):
        discord_messages = fit_log_lines_into_discord_messages(["No changes found"])
    # We don't expect many changes here since it will co-exist with periodic updates
    await interaction.followup.send(discord_messages[0])


def sync_members(guild: discord.Guild, storage: IngotsStorage) -> list[str]:
    # Perform a cross join between current Discord members and
    # entries in the sheet.
    # First, read all members from Discord.
    output = []
    members = []
    member_ids = []

    for member in guild.members:
        if validate_member_has_role(member, ROLES.MEMBER):
            members.append(member)
            member_ids.append(member.id)

    # Then, get all current entries from storage.
    try:
        existing = storage.read_members()
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
                output.append(f"skipped user {member.name} because they don't have a nickname in Discord")
                continue
            new_members.append(
                    Member(
                            id=int(member.id),
                            runescape_name=normalize_discord_string(member.nick).lower(),
                            ingots=0,
                    )
            )
            output.append(f"added user {normalize_discord_string(member.nick).lower()} because they joined")

    try:
        storage.add_members(new_members, "User Joined Server")
    except StorageError as error:
        logger.error(f"Encountered error writing new members: {error}")
        raise

    # Okay, now for all the users who have left.
    leaving_members = []
    for existing_member in existing:
        if existing_member.id not in member_ids:
            leaving_members.append(existing_member)
            output.append(f"removed user {existing_member.runescape_name} because they left the server")

    try:
        storage.remove_members(leaving_members, "User Left Server")
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
                                        runescape_name=normalize_discord_string(member.name).lower(),
                                        ingots=existing_member.ingots,
                                )
                        )
                else:
                    if normalize_discord_string(member.nick).lower() != existing_member.runescape_name:
                        changed_members.append(
                                Member(
                                        id=existing_member.id,
                                        runescape_name=normalize_discord_string(member.nick).lower(),
                                        ingots=existing_member.ingots,
                                )
                        )

    for changed_member in changed_members:
        output.append(f"updated RSN for {changed_member.runescape_name}")

    try:
        storage.update_members(changed_members, "Name Change")
    except StorageError as error:
        logger.error(f"Encountered error updating changed members: {error}")
        raise

    return output
