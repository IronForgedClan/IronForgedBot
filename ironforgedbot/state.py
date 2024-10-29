import json
import logging
import os
import sys
from typing import TypedDict

import aiofiles

from ironforgedbot.event_emitter import event_emitter

logger = logging.getLogger(__name__)


class BotStateDict(TypedDict):
    is_shutting_down: bool
    rate_limit: dict
    trick_or_treat_jackpot_claimed: bool


class BotState:
    _instance = None
    _file_path = "state.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BotState, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.state: BotStateDict = {
            "is_shutting_down": False,
            "rate_limit": dict(),
            "trick_or_treat_jackpot_claimed": False,
        }

        event_emitter.on("shutdown", self._save_state, priority=90)

    async def _save_state(self):
        try:
            async with aiofiles.open(self._file_path, "w") as file:
                # reset shut down flag so we don't get stuck
                self.state["is_shutting_down"] = False
                await file.write(json.dumps(self.state))

            logger.info(f"State saved to {self._file_path}")
        except Exception as e:
            logger.critical(f"Error saving state: {e}")

    async def load_state(self):
        if os.path.exists(self._file_path):
            try:
                async with aiofiles.open(self._file_path, "r") as file:
                    content = json.loads(await file.read())

                    if content.keys() != self.state.keys():
                        logger.warning("Invalid state file, using default state object")
                        return

                    self.state = content

                logger.info(f"State loaded from: {self._file_path}")
            except Exception as e:
                logger.critical(f"Error loading state: {e}")
        else:
            logger.info(
                f"No previous state file found at {self._file_path}. "
                "Starting with a default state."
            )


try:
    STATE = BotState()
except Exception as e:
    logger.critical(e)
    sys.exit(1)
