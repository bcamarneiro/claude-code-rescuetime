import tempfile
import unittest
from pathlib import Path
from unittest import mock

import rt_claude.config as cfgmod
import rt_claude.cli as cli


class TestFirstRunNotice(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cfgmod.STATE_DIR
        cfgmod.STATE_DIR = Path(self._tmp.name) / "rescuetime"

    def tearDown(self):
        cfgmod.STATE_DIR = self._orig
        self._tmp.cleanup()

    def test_no_key_nonwindows_nudges_setup(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value=None):
            msg = cli._first_run_notice("linux")
        self.assertIsNotNone(msg)
        self.assertIn("/rescuetime-setup", msg)
        self.assertNotIn(cli.ISSUE_URL, msg)

    def test_no_key_windows_has_both(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value=None):
            msg = cli._first_run_notice("win32")
        self.assertIn("/rescuetime-setup", msg)
        self.assertIn(cli.ISSUE_URL, msg)

    def test_key_present_nonwindows_is_none(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value="k"):
            self.assertIsNone(cli._first_run_notice("linux"))
        # No marker written → can still fire later
        self.assertFalse((cfgmod.STATE_DIR / "first-run-notice-shown").exists())

    def test_key_present_windows_shows_caveat_only(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value="k"):
            msg = cli._first_run_notice("win32")
        self.assertIn(cli.ISSUE_URL, msg)
        self.assertNotIn("/rescuetime-setup", msg)

    def test_fires_once(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value=None):
            self.assertIsNotNone(cli._first_run_notice("win32"))
            self.assertIsNone(cli._first_run_notice("win32"))
