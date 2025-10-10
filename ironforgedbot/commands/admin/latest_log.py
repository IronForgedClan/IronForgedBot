import logging
import os

import discord

from ironforgedbot.logging_config import get_logger_instance

logger = logging.getLogger(__name__)


def get_latest_log_file() -> discord.File | None:
    """Returns most recent log file as discord.File object"""
    try:
        log_dir = get_logger_instance().log_dir
        files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        files = [f for f in files if os.path.isfile(f)]

        if not files:
            logger.error("No log files found in directory: %s", log_dir)
            return None

        latest_file = max(files, key=os.path.getmtime)
        logger.debug("Retrieved latest log file: %s", latest_file)
        return discord.File(latest_file)
    except FileNotFoundError:
        logger.error("Log directory not found: %s", log_dir)
        return None
    except PermissionError as e:
        logger.error("Permission denied accessing log files: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error retrieving log file: %s", e)
        return None
