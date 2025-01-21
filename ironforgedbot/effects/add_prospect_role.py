from datetime import datetime, timezone
import logging
import discord

from ironforgedbot.common.helpers import (
    iso_timestamp_to_discord_relative,
    normalize_discord_string,
)
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_prospect_role(
    report_channel: discord.TextChannel, member: discord.Member
):
    await report_channel.send(
        f":information: {member.mention} has been given the "
        f"{text_bold(ROLE.PROSPECT)} role, saving timestamp..."
    )

    storage_member = None
    error = False
    try:
        storage_member = await STORAGE.read_member(
            normalize_discord_string(member.display_name)
        )
    except StorageError:
        error = True

    if error or not storage_member:
        return await report_channel.send(
            f":warning: {text_bold('WARNING')}\nAdded the "
            f"{text_bold(ROLE.PROSPECT)} role to a member that doesn't exist in "
            f"storage. Timestamp can therefore not be saved.\n\n"
            f"Please make sure the member {member.mention} has the "
            f"{text_bold(ROLE.MEMBER)} role and has been successfully synchonized. "
            f"Then add the {text_bold(ROLE.PROSPECT)} role again to successfully "
            "save a timestamp. Adding both roles at once is only supported on mobile."
        )

    timestamp = datetime.now(timezone.utc).isoformat()
    storage_member.joined_date = timestamp

    await STORAGE.update_members([storage_member], "BOT", "Added Prospect role")

    return await report_channel.send(
        f":information: Timestamp for {member.mention} "
        f"saved: {iso_timestamp_to_discord_relative(timestamp)}"
    )
