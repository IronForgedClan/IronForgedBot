import os
import sys

from ironforgedcore.config import BaseConfig


class ApiConfig(BaseConfig):
    def __init__(self) -> None:
        super().__init__()

        self.api_version: str = self.versions["api"]

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
