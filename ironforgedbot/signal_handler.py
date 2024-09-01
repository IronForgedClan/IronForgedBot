import logging
import signal
import sys

from ironforgedbot.storage.sheets import STORAGE

logger = logging.getLogger(__name__)

class SignalHandler:
    def __init__(self):
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)

    def graceful_shutdown(self, signum, frame):
        logger.info("Received shutdown command, cleaning up...")
        STORAGE.shutdown()
        logger.info("Shutting down.")
        sys.exit(0)
