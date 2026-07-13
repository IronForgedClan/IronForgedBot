import os
import sys

from ironforgedbot.config import CONFIG, Config

from api.version import get_api_version


class ApiConfig:
    def __init__(self, base: Config | None = None):
        self.base: Config = base if base is not None else CONFIG
        self.api_version: str = get_api_version()

        self.API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
        self.API_PORT: int = int(os.getenv("API_PORT") or 8080)
        self.API_RATE_LIMIT: int = int(os.getenv("API_RATE_LIMIT") or 30)
        origins = os.getenv("API_CORS_ORIGINS", "")
        self.API_CORS_ORIGINS: list[str] = [
            o.strip() for o in origins.split(",") if o.strip()
        ]
        trusted_hosts = os.getenv("API_TRUSTED_HOSTS", "127.0.0.1")
        self.API_TRUSTED_HOSTS: list[str] = [
            h.strip() for h in trusted_hosts.split(",") if h.strip()
        ]


try:
    API_CONFIG = ApiConfig()
except Exception as e:
    print(f"Failed to load API config: {e}", file=sys.stderr)
    sys.exit(1)
