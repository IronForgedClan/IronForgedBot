import logging
import unittest

if __name__ == "__main__":
    logging.disable(logging.CRITICAL)

    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover("tests", "*_test.py")

    test_runner = unittest.TextTestRunner()
    test_runner.run(test_suite)
