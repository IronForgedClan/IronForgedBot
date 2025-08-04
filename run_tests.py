import logging
import os
import sys
import unittest
from unittest.mock import patch

from tests.helpers import VALID_CONFIG


def run_tests() -> bool:
    with patch.dict(os.environ, VALID_CONFIG):
        logging.disable(logging.CRITICAL)

        test_loader = unittest.TestLoader()
        test_suite = test_loader.discover("tests", "*_test.py")

        test_runner = unittest.TextTestRunner()
        result = test_runner.run(test_suite)

        if result.wasSuccessful():
            return False
        else:
            return True


if __name__ == "__main__":
    sys.exit(run_tests())
