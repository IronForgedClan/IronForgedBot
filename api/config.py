import os
import sys

from ironforgedbot.config import CONFIG, Config, ENVIRONMENT

from api.version import get_api_version


class ApiConfig:
    def __init__(self, base: Config | None = None):
        self.base: Config = base if base is not None else CONFIG
        self.api_version: str = get_api_version()

        self.API_ENABLED: bool = os.getenv("API_ENABLED", "False") == "True"
        self.API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
        self.API_PORT: int = int(os.getenv("API_PORT") or 8080)
        self.API_RATE_LIMIT_PER_MINUTE: int = int(
            os.getenv("API_RATE_LIMIT_PER_MINUTE") or 60
        )
        pre_auth_env = os.getenv("API_PRE_AUTH_RATE_LIMIT_PER_MINUTE")
        if pre_auth_env is None:
            self.API_PRE_AUTH_RATE_LIMIT_PER_MINUTE: int = (
                self.API_RATE_LIMIT_PER_MINUTE
            )
        else:
            self.API_PRE_AUTH_RATE_LIMIT_PER_MINUTE: int = int(pre_auth_env)
        self.API_AUDIT_LOG_ENABLED: bool = (
            os.getenv("API_AUDIT_LOG_ENABLED", "True") == "True"
        )
        trusted = os.getenv("API_TRUSTED_PROXIES", "")
        self.API_TRUSTED_PROXIES: list[str] = [
            ip.strip() for ip in trusted.split(",") if ip.strip()
        ]
        docs_env = os.getenv("API_DOCS_ENABLED")
        if docs_env is None:
            self.API_DOCS_ENABLED = self.base.ENVIRONMENT != ENVIRONMENT.PRODUCTION
        else:
            self.API_DOCS_ENABLED = docs_env == "True"
        origins = os.getenv("API_CORS_ORIGINS", "")
        self.API_CORS_ORIGINS: list[str] = [
            o.strip() for o in origins.split(",") if o.strip()
        ]


try:
    API_CONFIG = ApiConfig()
except Exception as e:
    print(f"Failed to load API config: {e}", file=sys.stderr)
    sys.exit(1)
