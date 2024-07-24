import logging
import os

from concurrent_log_handler import ConcurrentRotatingFileHandler


def configure_logging():
    if not os.path.exists("./logs"):
        os.makedirs("./logs")

    logging.basicConfig(level=logging.INFO, encoding="utf-8")

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = ConcurrentRotatingFileHandler(
        "./logs/bot.log", maxBytes=100_000, backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


configure_logging()
