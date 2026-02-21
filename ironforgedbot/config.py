import enum
import logging
import os
import sys

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ENVIRONMENT(enum.StrEnum):
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"


class Config:
    def __init__(self):
        load_dotenv()

        self.BOT_VERSION: str = self.get_bot_version()
        self.ENVIRONMENT: ENVIRONMENT = ENVIRONMENT(os.getenv("ENVIRONMENT", "prod"))
        self.TEMP_DIR: str = os.getenv("TEMP_DIR", "./temp")
        self.SHEET_ID: str = os.getenv("SHEET_ID", "")
        self.GUILD_ID: int = int(os.getenv("GUILD_ID") or 0)
        self.BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
        self.WOM_GROUP_ID: int = int(os.getenv("WOM_GROUP_ID") or 0)
        self.WOM_API_KEY: str = os.getenv("WOM_API_KEY", "")
        self.AUTOMATION_CHANNEL_ID: int = int(os.getenv("AUTOMATION_CHANNEL_ID") or 0)
        self.RAFFLE_CHANNEL_ID: int = int(os.getenv("RAFFLE_CHANNEL_ID") or 0)
        self.INGOT_SHOP_CHANNEL_ID: int = int(os.getenv("INGOT_SHOP_CHANNEL_ID") or 0)
        self.RULES_CHANNEL_ID: int = int(os.getenv("RULES_CHANNEL_ID") or 0)
        self.TRICK_OR_TREAT_ENABLED: bool = (
            os.getenv("TRICK_OR_TREAT_ENABLED", "False") == "True"
        )
        self.TRICK_OR_TREAT_CHANNEL_ID: int = (
            int(os.getenv("TRICK_OR_TREAT_CHANNEL_ID") or 0)
            if self.TRICK_OR_TREAT_ENABLED
            else 1
        )
        self.TRICK_OR_TREAT_COOLDOWN_SECONDS: int = int(
            os.getenv("TRICK_OR_TREAT_COOLDOWN_SECONDS") or 3600
        )

        # Standard cron format: "minute hour day month day_of_week"
        # All times are in UTC
        self.CRON_SYNC_MEMBERS: str = os.getenv("CRON_SYNC_MEMBERS", "50 3,15 * * *")
        self.CRON_REFRESH_RANKS: str = os.getenv("CRON_REFRESH_RANKS", "10 4,16 * * *")
        self.CRON_CHECK_ACTIVITY: str = os.getenv("CRON_CHECK_ACTIVITY", "0 1 * * 1")
        self.CRON_CHECK_DISCREPANCIES: str = os.getenv(
            "CRON_CHECK_DISCREPANCIES", "0 0 * * 0"
        )
        self.CRON_CLEAR_CACHES: str = os.getenv("CRON_CLEAR_CACHES", "*/10 * * * *")
        self.CRON_PAYROLL: str = os.getenv("CRON_PAYROLL", "0 6 1 * *")

        self.validate_config()

    def validate_config(self):
        for key, value in vars(self).items():
            if key.startswith("CRON_"):
                # Skip validation for CRON_ variables (APScheduler will validate)
                continue
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
