import logging
import os
import discord

from ironforgedbot.common.helpers import (
    normalize_discord_string,
    validate_member_has_role,
    validate_protected_request,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.config import CONFIG
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError, Member


logger = logging.getLogger(__name__)


async def sync_members(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        _, caller = validate_protected_request(
            interaction, interaction.user.display_name, ROLES.LEADERSHIP
        )
    except (ReferenceError, ValueError) as error:
        logger.info(
            f"Member '{interaction.user.display_name}' tried syncmembers but does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    output = ""
    logger.info(f"Handling '/syncmembers' on behalf of {caller}")

    # Perform a cross join between current Discord members and
    # entries in the sheet.
    # First, read all members from Discord.
    members = []
    member_ids = []

    assert interaction.guild is not None
    for member in interaction.guild.members:
        if validate_member_has_role(member, ROLES.MEMBER):
            members.append(member)
            member_ids.append(member.id)

    # Then, get all current entries from storage.
    try:
        existing = STORAGE.read_members()
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error reading members: {error}"
        )
        return

    written_ids = [member.id for member in existing]

    # Now for the actual diffing.
    # First, what new members are in Discord but not the sheet?
    new_members = []
    for member in members:
        if member.id not in written_ids:
            # Don't allow users without a nickname into storage.
            if not member.nick or len(member.nick) < 1:
                output += f"skipped user {member.name} because they don't have a nickname in Discord\n"
                continue
            new_members.append(
                Member(
                    id=int(member.id),
                    runescape_name=normalize_discord_string(member.nick).lower(),
                    ingots=0,
                )
            )
            output += f"added user {normalize_discord_string(member.nick).lower()} because they joined\n"

    try:
        STORAGE.add_members(new_members, "User Joined Server")
    except StorageError as e:
        await interaction.followup.send(f"Encountered error writing new members: {e}")
        return

    # Okay, now for all the users who have left.
    leaving_members = []
    for existing_member in existing:
        if existing_member.id not in member_ids:
            leaving_members.append(existing_member)
            output += f"removed user {existing_member.runescape_name} because they left the server\n"
    try:
        STORAGE.remove_members(leaving_members, "User Left Server")
    except StorageError as e:
        await interaction.followup.send(f"Encountered error removing members: {e}")
        return

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
                                runescape_name=member.name.lower(),
                                ingots=existing_member.ingots,
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
                            )
                        )

    for changed_member in changed_members:
        output += f"updated RSN for {changed_member.runescape_name}\n"

    try:
        STORAGE.update_members(changed_members, "Name Change")
    except StorageError as e:
        await interaction.followup.send(
            f"Encountered error updating changed members: {e}"
        )
        return

    path = os.path.join(CONFIG.TEMP_DIR, f"syncmembers_{caller}.txt")
    with open(path, "w") as f:
        f.write(output)

    with open(path, "rb") as f:
        discord_file = discord.File(f, filename="syncmembers.txt")
        await interaction.followup.send(
            "Successfully synced ingots storage with current members!",
            file=discord_file,
        )
