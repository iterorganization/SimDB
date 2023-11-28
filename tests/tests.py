import unittest

from . import test_cli


def suite():
    suite = unittest.TestSuite()
    suite.addTest(test_cli.suite())
    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(suite())
