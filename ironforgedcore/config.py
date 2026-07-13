import enum
import json
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ENVIRONMENT(enum.StrEnum):
    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"


class BaseConfig:
    """Shared configuration base. Subclasses add package-specific fields."""

    def __init__(self) -> None:
        load_dotenv()

        self.ENVIRONMENT: ENVIRONMENT = ENVIRONMENT(os.getenv("ENVIRONMENT", "prod"))
        self.DATABASE_URL: Optional[str] = self._resolve_database_url()
        self.versions: dict[str, str] = self._load_versions()

    def _resolve_database_url(self) -> Optional[str]:
        url = os.getenv("DATABASE_URL")
        if url:
            return url

        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASS")
        db_name = os.getenv("DB_NAME")
        db_host = os.getenv("DB_HOST", "localhost")

        if db_user and db_pass and db_name:
            return f"mysql+aiomysql://{db_user}:{db_pass}@{db_host}/{db_name}"

        return None

    def _load_versions(self) -> dict[str, str]:
        with open("versions.json", "r") as file:
            return json.load(file)
