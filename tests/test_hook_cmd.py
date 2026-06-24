import json
import sys
import io
import os
import importlib
import tempfile
import contextlib
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestHookCmd(unittest.TestCase):
    def setUp(self):
        self._orig_home = os.environ.get("HOME")
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["HOME"] = self._tmpdir.name
        # Reload modules so STATE_DIR etc. pick up the new HOME
        import rt_claude.config as config_mod
        importlib.reload(config_mod)
        import rt_claude.state as state_mod
        importlib.reload(state_mod)
        import rt_claude.cli as cli_mod
        importlib.reload(cli_mod)
        self.cli = cli_mod
        self.state = state_mod

    def tearDown(self):
        if self._orig_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._orig_home
        self._tmpdir.cleanup()
        # Reload so subsequent tests/imports get original HOME
        import rt_claude.config as config_mod
        importlib.reload(config_mod)
        import rt_claude.state as state_mod
        importlib.reload(state_mod)
        import rt_claude.cli as cli_mod
        importlib.reload(cli_mod)

    def _feed_stdin(self, payload):
        return unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload)))

    def test_hook_dry_run_prints_would_post(self):
        buf = io.StringIO()
        payload = {"session_id": "s1", "cwd": self._tmpdir.name}
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            with contextlib.redirect_stdout(buf):
                rc = self.cli.main(["--dry-run", "hook", "--event", "SessionStart"])
        self.assertEqual(rc, 0)
        self.assertIn("WOULD POST", buf.getvalue())

    def test_hook_no_key_is_noop_exit_0(self):
        payload = {"session_id": "s2", "cwd": self._tmpdir.name}
        env_bak = os.environ.pop("RESCUETIME_API_KEY", None)
        try:
            with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
                rc = self.cli.main(["hook", "--event", "SessionStart"])
        finally:
            if env_bak is not None:
                os.environ["RESCUETIME_API_KEY"] = env_bak
        self.assertEqual(rc, 0)

    def test_hook_malformed_stdin_exit_0(self):
        with unittest.mock.patch("sys.stdin", io.StringIO("not json")):
            rc = self.cli.main(["hook", "--event", "Stop"])
        self.assertEqual(rc, 0)

    def test_session_end_clears_state(self):
        import rt_claude.config as config_mod
        sessions_dir = config_mod.STATE_DIR / "sessions"
        self.state.save_session("s3", {"last_context": "x@y"}, sessions_dir)
        payload = {"session_id": "s3", "cwd": self._tmpdir.name}
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            self.cli.main(["hook", "--event", "SessionEnd"])
        self.assertEqual(self.state.load_session("s3", sessions_dir), {})


if __name__ == "__main__":
    unittest.main()
