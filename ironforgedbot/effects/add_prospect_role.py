from datetime import datetime, timezone
import logging
import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_prospect_role(member: discord.Member):
    logger.info(f"{member.display_name} has been made a prospect")

    try:
        storage_member = await STORAGE.read_member(
            normalize_discord_string(member.display_name)
        )
    except StorageError as e:
        logger.error(e)
        return

    assert storage_member
    storage_member.joined_date = datetime.now(timezone.utc).isoformat()

    return await STORAGE.update_members([storage_member], "BOT", "Added Prospect role")
