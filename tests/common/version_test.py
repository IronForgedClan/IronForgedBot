import importlib
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


def _read_pyproject_version(pkg_dir: str) -> str:
    pyproject_path = Path(__file__).parent.parent.parent / pkg_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)["project"]["version"]


class TestPackageVersions(unittest.TestCase):
    def test_ironforgedbot_version_is_non_empty_string(self):
        import ironforgedbot

        self.assertIsInstance(ironforgedbot.__version__, str)
        self.assertGreater(len(ironforgedbot.__version__), 0)

    def test_api_version_is_non_empty_string(self):
        import api

        self.assertIsInstance(api.__version__, str)
        self.assertGreater(len(api.__version__), 0)

    def test_ironforgedbot_version_matches_pyproject(self):
        import ironforgedbot

        expected = _read_pyproject_version("ironforgedbot")
        self.assertEqual(ironforgedbot.__version__, expected)

    def test_api_version_matches_pyproject(self):
        import api

        expected = _read_pyproject_version("api")
        self.assertEqual(api.__version__, expected)

    def test_ironforgedbot_falls_back_to_pyproject_when_not_installed(self):
        import ironforgedbot

        original = ironforgedbot.__version__
        expected = _read_pyproject_version("ironforgedbot")
        with patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("ironforgedbot"),
        ):
            reloaded = importlib.reload(ironforgedbot)

        try:
            self.assertEqual(reloaded.__version__, expected)
        finally:
            reloaded.__version__ = original

    def test_api_falls_back_to_pyproject_when_not_installed(self):
        import api

        original = api.__version__
        expected = _read_pyproject_version("api")
        with patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("ironforgedapi"),
        ):
            reloaded = importlib.reload(api)

        try:
            self.assertEqual(reloaded.__version__, expected)
        finally:
            reloaded.__version__ = original


class TestConfigUsesVersion(unittest.TestCase):
    def test_bot_config_uses_package_version(self):
        import ironforgedbot
        from tests.helpers import VALID_CONFIG

        with patch.dict("os.environ", VALID_CONFIG), patch(
            "ironforgedcore.config.load_dotenv"
        ):
            from ironforgedbot.config import Config

            result = Config()

        self.assertEqual(result.BOT_VERSION, ironforgedbot.__version__)

    def test_api_config_uses_package_version(self):
        import api
        from tests.helpers import VALID_CONFIG

        with patch.dict("os.environ", VALID_CONFIG), patch(
            "ironforgedcore.config.load_dotenv"
        ):
            from api.config import ApiConfig

            result = ApiConfig()

        self.assertEqual(result.api_version, api.__version__)


if __name__ == "__main__":
    unittest.main()
