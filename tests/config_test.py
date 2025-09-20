import copy
import unittest
from unittest.mock import mock_open, patch

from ironforgedbot.config import Config, ENVIRONMENT
from tests.helpers import VALID_CONFIG


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.valid_config = VALID_CONFIG.copy()
        self.invalid_str_config = copy.copy(VALID_CONFIG)
        self.invalid_str_config["SHEET_ID"] = ""
        self.invalid_int_config = copy.copy(VALID_CONFIG)
        self.invalid_int_config["GUILD_ID"] = ""

    @patch.dict("os.environ", VALID_CONFIG)
    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="1.0.0")
    def test_creates_config_with_valid_environment(self, mock_file, mock_dotenv):
        result = Config()

        self.assertIsNotNone(result)
        self.assertEqual(result.TEMP_DIR, VALID_CONFIG["TEMP_DIR"])
        self.assertEqual(result.SHEET_ID, VALID_CONFIG["SHEET_ID"])
        self.assertEqual(result.GUILD_ID, int(VALID_CONFIG["GUILD_ID"]))
        self.assertEqual(result.BOT_TOKEN, VALID_CONFIG["BOT_TOKEN"])
        self.assertEqual(result.WOM_GROUP_ID, int(VALID_CONFIG["WOM_GROUP_ID"]))
        self.assertEqual(result.WOM_API_KEY, VALID_CONFIG["WOM_API_KEY"])
        self.assertEqual(result.AUTOMATION_CHANNEL_ID, int(VALID_CONFIG["AUTOMATION_CHANNEL_ID"]))
        self.assertEqual(result.BOT_VERSION, "1.0.0")
        mock_file.assert_called_once_with("VERSION", "r")
        mock_dotenv.assert_called_once()

    def test_raises_value_error_for_empty_string_field(self):
        with patch.dict("os.environ", self.invalid_str_config):
            with self.assertRaises(ValueError) as context:
                Config()
            
            self.assertEqual(
                str(context.exception), 
                "Configuration key 'SHEET_ID' (str) is missing or empty"
            )

    def test_raises_value_error_for_empty_int_field(self):
        with patch.dict("os.environ", self.invalid_int_config):
            with self.assertRaises(ValueError) as context:
                Config()
            
            self.assertEqual(
                str(context.exception), 
                "Configuration key 'GUILD_ID' (int) is missing or empty"
            )

    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="2.1.5")
    def test_reads_version_from_file(self, mock_file, mock_dotenv):
        with patch.dict("os.environ", self.valid_config):
            result = Config()
            
            self.assertEqual(result.BOT_VERSION, "2.1.5")
            mock_file.assert_called_once_with("VERSION", "r")
            mock_dotenv.assert_called_once()

    @patch.dict("os.environ", {**VALID_CONFIG, "ENVIRONMENT": "dev"})
    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="1.0.0")
    def test_sets_development_environment(self, mock_file, mock_dotenv):
        result = Config()
        
        self.assertEqual(result.ENVIRONMENT, ENVIRONMENT.DEVELOPMENT)

    @patch.dict("os.environ", {**VALID_CONFIG, "ENVIRONMENT": "staging"})
    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="1.0.0")
    def test_sets_staging_environment(self, mock_file, mock_dotenv):
        result = Config()
        
        self.assertEqual(result.ENVIRONMENT, ENVIRONMENT.STAGING)

    @patch.dict("os.environ", {**VALID_CONFIG, "TRICK_OR_TREAT_ENABLED": "True", "TRICK_OR_TREAT_CHANNEL_ID": "999"})
    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="1.0.0")
    def test_enables_trick_or_treat_feature(self, mock_file, mock_dotenv):
        result = Config()
        
        self.assertTrue(result.TRICK_OR_TREAT_ENABLED)
        self.assertEqual(result.TRICK_OR_TREAT_CHANNEL_ID, 999)

    @patch.dict("os.environ", {**VALID_CONFIG, "TRICK_OR_TREAT_ENABLED": "False"})
    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="1.0.0")
    def test_disables_trick_or_treat_feature(self, mock_file, mock_dotenv):
        result = Config()
        
        self.assertFalse(result.TRICK_OR_TREAT_ENABLED)
        self.assertEqual(result.TRICK_OR_TREAT_CHANNEL_ID, 1)

    @patch.dict("os.environ", {**VALID_CONFIG, "TRICK_OR_TREAT_COOLDOWN_SECONDS": "7200"})
    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", new_callable=mock_open, read_data="1.0.0")
    def test_sets_trick_or_treat_cooldown(self, mock_file, mock_dotenv):
        result = Config()
        
        self.assertEqual(result.TRICK_OR_TREAT_COOLDOWN_SECONDS, 7200)

    @patch("ironforgedbot.config.load_dotenv")
    @patch("builtins.open", side_effect=FileNotFoundError("VERSION file not found"))
    def test_handles_missing_version_file(self, mock_file, mock_dotenv):
        with patch.dict("os.environ", self.valid_config):
            with self.assertRaises(FileNotFoundError):
                Config()
            
            mock_file.assert_called_with("VERSION", "r")

    def test_validates_all_required_fields(self):
        missing_token_config = self.valid_config.copy()
        missing_token_config["BOT_TOKEN"] = ""
        
        with patch.dict("os.environ", missing_token_config):
            with self.assertRaises(ValueError) as context:
                Config()
            
            self.assertIn("BOT_TOKEN", str(context.exception))