import importlib
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch


def _read_pyproject_version() -> str:
    pyproject_path = Path(__file__).parent.parent / "ironforgedbot" / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)["project"]["version"]


class TestBotPackageVersion(unittest.TestCase):
    def test_ironforgedbot_version_is_non_empty_string(self):
        import ironforgedbot

        self.assertIsInstance(ironforgedbot.__version__, str)
        self.assertGreater(len(ironforgedbot.__version__), 0)

    def test_ironforgedbot_version_matches_pyproject(self):
        import ironforgedbot

        expected = _read_pyproject_version()
        self.assertEqual(ironforgedbot.__version__, expected)

    def test_ironforgedbot_falls_back_to_pyproject_when_not_installed(self):
        import ironforgedbot

        original = ironforgedbot.__version__
        expected = _read_pyproject_version()
        with patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("ironforgedbot"),
        ):
            reloaded = importlib.reload(ironforgedbot)

        try:
            self.assertEqual(reloaded.__version__, expected)
        finally:
            reloaded.__version__ = original


if __name__ == "__main__":
    unittest.main()
