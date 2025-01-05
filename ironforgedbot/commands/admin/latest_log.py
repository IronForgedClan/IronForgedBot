import logging
import os

import discord

from ironforgedbot.logging_config import LOG_DIR

logger = logging.getLogger(__name__)


def get_latest_log_file() -> discord.File | None:
    """Returns most recent log file as discord.File object"""
    try:
        files = [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR)]
        files = [f for f in files if os.path.isfile(f)]
        latest_file = max(files, key=os.path.getmtime)

        return discord.File(latest_file)
    except Exception as e:
        logger.error(e)
        return None
