from datetime import datetime, timezone
import logging
import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.roles import ROLE
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_prospect_role(
    report_channel: discord.TextChannel, member: discord.Member
):
    await report_channel.send(
        f":information: {member.mention} has been given the "
        f"{ROLE.PROSPECT} role, saving timestamp."
    )

    try:
        storage_member = await STORAGE.read_member(
            normalize_discord_string(member.display_name)
        )
    except StorageError as e:
        logger.error(e)
        await report_channel.send("An error occured. Please contact the Discord Team.")
        return

    if not storage_member:
        await report_channel.send("An error occured. Please contact the Discord Team.")
        return

    storage_member.joined_date = datetime.now(timezone.utc).isoformat()

    return await STORAGE.update_members([storage_member], "BOT", "Added Prospect role")
