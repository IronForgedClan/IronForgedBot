import logging
import os

from concurrent_log_handler import ConcurrentRotatingFileHandler

from ironforgedbot.event_emitter import event_emitter

LOG_DIR = "./logs"

log = logging.getLogger(__name__)


class IronForgedLogger:
    def __init__(self):
        self.log_dir = LOG_DIR
        self.file_handler = ConcurrentRotatingFileHandler(
            f"{self.log_dir}/bot.log", maxBytes=100_000, backupCount=10
        )

        self.configure_logging()
        event_emitter.on("shutdown", self.cleanup, priority=100)

    def configure_logging(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        logging.basicConfig(level=logging.INFO, encoding="utf-8")

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        self.file_handler.setLevel(logging.INFO)
        self.file_handler.setFormatter(formatter)

        logger = logging.getLogger()
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.addHandler(self.file_handler)

    async def cleanup(self):
        log.info("Closing logging file handler...")
        self.file_handler.close()


logger = IronForgedLogger()
