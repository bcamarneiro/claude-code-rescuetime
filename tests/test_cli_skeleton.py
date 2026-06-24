import subprocess
import sys
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCliSkeleton(unittest.TestCase):
    def test_help_returns_0_and_contains_subcommands(self):
        result = subprocess.run(
            [sys.executable, "-m", "rt_claude", "--help"],
            capture_output=True,
            text=True,
            cwd=REPO,
        )
        self.assertEqual(result.returncode, 0)
        output = result.stdout
        for cmd in ["hook", "install", "uninstall", "test", "status"]:
            self.assertIn(cmd, output, msg="'{}' not found in --help output".format(cmd))


if __name__ == "__main__":
    unittest.main()
