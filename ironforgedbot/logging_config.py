import json
import logging
import os
from typing import Dict, Optional, Any

from concurrent_log_handler import ConcurrentRotatingFileHandler

from ironforgedbot.event_emitter import event_emitter


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


class IronForgedLogger:
    """Centralized logging configuration for IronForged Bot."""

    # Default configurations that can be overridden via environment variables
    DEFAULT_LOG_DIR = "./logs"
    DEFAULT_LOG_LEVEL = "INFO"
    DEFAULT_FILE_MAX_BYTES = 10_000_000  # 10MB
    DEFAULT_FILE_BACKUP_COUNT = 10
    DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # Third-party loggers to suppress or configure
    THIRD_PARTY_LOGGERS: Dict[str, Dict[str, Any]] = {
        "sqlalchemy.engine": {"level": logging.ERROR, "propagate": False},
        "discord.client": {"propagate": False},
        "discord.gateway": {"propagate": False},
        "discord.http": {"level": logging.WARNING},
        "discord": {"level": logging.ERROR},
        "apscheduler.scheduler": {"propagate": False},
        "apscheduler.executors": {"propagate": False},
        "googleapiclient": {"level": logging.ERROR},
    }

    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_level: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        """Initialize logger with configurable settings.

        Args:
            log_dir: Directory for log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            environment: Environment name (dev, staging, prod)
        """
        self.log_dir = log_dir or os.getenv("LOG_DIR", self.DEFAULT_LOG_DIR)
        self.log_level = getattr(
            logging,
            (log_level or os.getenv("LOG_LEVEL", self.DEFAULT_LOG_LEVEL)).upper(),
        )
        self.environment = environment or os.getenv("ENVIRONMENT", "prod")
        self.use_json_format = os.getenv("LOG_JSON_FORMAT", "false").lower() == "true"

        # Configure file handler
        self.file_handler = self._create_file_handler()

        # Configure logging
        self.configure_logging()

        # Register cleanup handler
        event_emitter.on("shutdown", self.cleanup, priority=100)

    def _create_file_handler(self) -> ConcurrentRotatingFileHandler:
        """Create and configure the file handler."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # Different log files for different environments
        log_filename = f"{self.log_dir}/bot_{self.environment}.log"

        return ConcurrentRotatingFileHandler(
            log_filename,
            maxBytes=int(os.getenv("LOG_FILE_MAX_BYTES", self.DEFAULT_FILE_MAX_BYTES)),
            backupCount=int(
                os.getenv("LOG_FILE_BACKUP_COUNT", self.DEFAULT_FILE_BACKUP_COUNT)
            ),
        )

    def configure_logging(self) -> None:
        """Configure the logging system."""
        # Configure root logger
        logging.basicConfig(
            level=self.log_level,
            encoding="utf-8",
            format=self.DEFAULT_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT,
        )

        # Create formatter
        if self.use_json_format and self.environment == "prod":
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(self.DEFAULT_FORMAT, self.DEFAULT_DATE_FORMAT)

        # Configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._get_console_log_level())
        console_handler.setFormatter(formatter)

        # Configure file handler
        self.file_handler.setLevel(self.log_level)
        self.file_handler.setFormatter(formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(console_handler)
        root_logger.addHandler(self.file_handler)

        # Configure third-party loggers
        self._configure_third_party_loggers()

        # Log initial configuration
        logger = logging.getLogger(__name__)
        logger.info(
            f"Logging configured for {self.environment} environment at level {logging.getLevelName(self.log_level)}"
        )

    def _get_console_log_level(self) -> int:
        """Get console log level based on environment."""
        # Allow override via environment variable
        console_level = os.getenv("LOG_CONSOLE_LEVEL")
        if console_level:
            return getattr(logging, console_level.upper())

        # Default based on environment
        if self.environment == "dev":
            return logging.DEBUG
        elif self.environment == "staging":
            return logging.INFO
        else:  # prod
            return logging.WARNING

    def _configure_third_party_loggers(self) -> None:
        """Configure third-party library loggers to reduce noise."""
        for logger_name, config in self.THIRD_PARTY_LOGGERS.items():
            logger = logging.getLogger(logger_name)

            if "level" in config:
                logger.setLevel(config["level"])

            if "propagate" in config:
                logger.propagate = config["propagate"]

    async def cleanup(self) -> None:
        """Clean up logging resources."""
        logger = logging.getLogger(__name__)
        logger.info("Closing logging file handler...")
        self.file_handler.close()

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance with the given name.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)


# Initialize the global logger configuration
# This will be imported at the start of main.py
_logger_instance = IronForgedLogger()

# Export LOG_DIR for backwards compatibility
LOG_DIR = _logger_instance.log_dir


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
