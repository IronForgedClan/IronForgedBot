import logging
import os
import sys

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        load_dotenv()

        self.BOT_VERSION: str = self.get_bot_version()
        self.DEBUG_COMMANDS: bool = os.getenv("ENVIRONMENT", "prod") == "dev"
        self.TEMP_DIR: str = os.getenv("TEMP_DIR", "./temp")
        self.SHEET_ID: str = os.getenv("SHEET_ID", "")
        self.GUILD_ID: int = int(os.getenv("GUILD_ID") or 0)
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
        self.WOM_GROUP_ID: int = int(os.getenv("WOM_GROUP_ID") or 0)
        self.WOM_API_KEY: str = os.getenv("WOM_API_KEY", "")
        self.AUTOMATION_CHANNEL_ID: int = int(os.getenv("AUTOMATION_CHANNEL_ID") or 0)
        self.TRICK_OR_TREAT_ENABLED: bool = (
            os.getenv("TRICK_OR_TREAT_ENABLED", "False") == "True"
        )
        self.TRICK_OR_TREAT_CHANNEL_ID: int = (
            int(os.getenv("TRICK_OR_TREAT_CHANNEL_ID") or 0)
            if self.TRICK_OR_TREAT_ENABLED
            else 1
        )

        self.validate_config()

    def validate_config(self):
        for key, value in vars(self).items():
            if isinstance(value, bool):
                continue
            if isinstance(value, str) and not value:
                raise ValueError(f"Configuration key '{key}' (str) is missing or empty")
            if isinstance(value, int) and value <= 0:
                raise ValueError(f"Configuration key '{key}' (int) is missing or empty")

    def get_bot_version(self) -> str:
        with open("VERSION", "r") as file:
            return file.read().strip()


try:
    CONFIG = Config()
    logger.info("Loaded local configuration successfully")
except Exception as e:
    logger.critical(e)
    sys.exit(1)
