import logging
import os

from concurrent_log_handler import ConcurrentRotatingFileHandler

LOG_DIR = "./logs"


def configure_logging():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    logging.basicConfig(level=logging.INFO, encoding="utf-8")

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # NOTE: Beware of backup counts greater than 25
    #       It will break /logs embed max fields
    file_handler = ConcurrentRotatingFileHandler(
        f"{LOG_DIR}/bot.log", maxBytes=100_000, backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


configure_logging()
