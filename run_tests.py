import logging
import os
import sys
import unittest
from unittest.mock import patch

from tests.helpers import VALID_CONFIG


def patch_env():
    env_patcher = patch.dict(os.environ, VALID_CONFIG)
    env_patcher.start()
    return env_patcher


def run_tests():
    logging.disable(logging.CRITICAL)
    patcher = patch_env()

    try:
        test_loader = unittest.TestLoader()
        test_suite = test_loader.discover("tests", "*_test.py")

        test_runner = unittest.TextTestRunner()
        result = test_runner.run(test_suite)

        if result.wasSuccessful():
            return 0
        else:
            return 1
    finally:
        patcher.stop()


if __name__ == "__main__":
    sys.exit(run_tests())
