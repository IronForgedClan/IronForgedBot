import logging
import os
import sys

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        load_dotenv()

        self.SHEET_ID: str = os.getenv("SHEET_ID", "")
        self.GUILD_ID: int = int(os.getenv("GUILD_ID", "0"))
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
        self.WOM_GROUP_ID: int = int(os.getenv("WOM_GROUP_ID", "0"))
        self.WOM_API_KEY: str = os.getenv("WOM_API_KEY", "")
        self.RANKS_UPDATE_CHANNEL: int = int(os.getenv("RANKS_UPDATE_CHANNEL", ""))

        self.validate_config()

    def validate_config(self):
        for key, value in vars(self).items():
            if isinstance(value, str) and not value:
                raise ValueError(f"Configuration key '{key}' is missing or empty")
            if isinstance(value, int) and value <= 0:
                raise ValueError(f"Configuration key '{key}' is missing or empty")


try:
    CONFIG = Config()
except ValueError as e:
    logger.critical(e)
    sys.exit(1)
