import os
import sys
import io
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import rt_claude.config as cfgmod
import rt_claude.cli as cli


class TestWriteApiKey(unittest.TestCase):
    def test_writes_stripped_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "api_key"
            cfgmod.write_api_key("  abc123  ", p)
            self.assertEqual(p.read_text(), "abc123")

    @unittest.skipIf(sys.platform == "win32", "POSIX permission check")
    def test_file_mode_is_600(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "api_key"
            cfgmod.write_api_key("k", p)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)


class TestCmdSetKey(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cfgmod.API_KEY_PATH
        cfgmod.API_KEY_PATH = Path(self._tmp.name) / "api_key"

    def tearDown(self):
        cfgmod.API_KEY_PATH = self._orig
        self._tmp.cleanup()

    def test_arg_key_saved_and_verified(self):
        args = mock.Mock(key="tok123")
        with mock.patch.object(cli, "post_highlight", return_value=200) as ph:
            rc = cli.cmd_set_key(args)
        self.assertEqual(rc, 0)
        self.assertEqual(cfgmod.API_KEY_PATH.read_text(), "tok123")
        ph.assert_called_once()

    def test_empty_key_rejected(self):
        args = mock.Mock(key="   ")
        rc = cli.cmd_set_key(args)
        self.assertEqual(rc, 1)
        self.assertFalse(cfgmod.API_KEY_PATH.exists())

    def test_save_succeeds_even_if_verify_fails(self):
        args = mock.Mock(key="tok")
        with mock.patch.object(cli, "post_highlight", side_effect=RuntimeError("net")):
            rc = cli.cmd_set_key(args)
        self.assertEqual(rc, 0)
        self.assertEqual(cfgmod.API_KEY_PATH.read_text(), "tok")
