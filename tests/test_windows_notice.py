import tempfile
import unittest
from pathlib import Path

import rt_claude.config as cfgmod
from rt_claude.cli import ISSUE_URL, _windows_first_run_notice


class TestWindowsNotice(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cfgmod.STATE_DIR
        cfgmod.STATE_DIR = Path(self._tmp.name) / "rescuetime"

    def tearDown(self):
        cfgmod.STATE_DIR = self._orig
        self._tmp.cleanup()

    def test_non_windows_returns_none(self):
        self.assertIsNone(_windows_first_run_notice("linux"))
        self.assertIsNone(_windows_first_run_notice("darwin"))

    def test_windows_shows_once_then_silent(self):
        first = _windows_first_run_notice("win32")
        self.assertIsNotNone(first)
        self.assertIn(ISSUE_URL, first)
        # Marker now exists → never fires again.
        self.assertIsNone(_windows_first_run_notice("win32"))


if __name__ == "__main__":
    unittest.main()
