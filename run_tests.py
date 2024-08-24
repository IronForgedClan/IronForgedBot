import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from tests.helpers import VALID_CONFIG


@patch(
    "google.oauth2.service_account.Credentials.from_service_account_file",
    new_callable=MagicMock,
)
@patch.dict(os.environ, VALID_CONFIG)
def run_tests(_):
    logging.disable(logging.CRITICAL)

    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover("tests", "*_test.py")

    test_runner = unittest.TextTestRunner()
    result = test_runner.run(test_suite)

    if result.wasSuccessful():
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
