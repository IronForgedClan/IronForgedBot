import unittest
import copy
from unittest.mock import patch

from ironforgedbot.config import Config
from tests.helpers import VALID_CONFIG

INVALID_STR_CONIG = copy.copy(VALID_CONFIG)
INVALID_STR_CONIG["SHEET_ID"] = ""

INVALID_INT_CONIG = copy.copy(VALID_CONFIG)
INVALID_INT_CONIG["GUILD_ID"] = ""


class TestConfig(unittest.TestCase):
    @patch.dict("os.environ", VALID_CONFIG)
    def test_valid_config(self):
        try:
            result = Config()
        except Exception as e:
            self.fail(f"Exception {e} raised unexpectedly")

        self.assertIsNotNone(result)
        self.assertEqual(result.TEMP_DIR, VALID_CONFIG["TEMP_DIR"])
        self.assertEqual(result.SHEET_ID, VALID_CONFIG["SHEET_ID"])
        self.assertEqual(result.GUILD_ID, int(VALID_CONFIG["GUILD_ID"]))
        self.assertEqual(result.BOT_TOKEN, VALID_CONFIG["BOT_TOKEN"])
        self.assertEqual(result.WOM_GROUP_ID, int(VALID_CONFIG["WOM_GROUP_ID"]))
        self.assertEqual(result.WOM_API_KEY, VALID_CONFIG["WOM_API_KEY"])
        self.assertEqual(
            result.RANKS_UPDATE_CHANNEL, VALID_CONFIG["RANKS_UPDATE_CHANNEL"]
        )

    @patch.dict("os.environ", INVALID_STR_CONIG)
    def test_raise_exception_bad_string(self):
        with self.assertRaises(ValueError) as cm:
            Config()

        self.assertEqual(
            str(cm.exception), "Configuration key 'SHEET_ID' is missing or empty"
        )

    @patch.dict("os.environ", INVALID_INT_CONIG)
    def test_raise_exception_bad_int(self):
        with self.assertRaises(ValueError) as cm:
            Config()

        self.assertEqual(
            str(cm.exception), "Configuration key 'GUILD_ID' is missing or empty"
        )
