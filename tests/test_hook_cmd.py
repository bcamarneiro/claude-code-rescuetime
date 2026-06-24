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
        os.environ.pop("RESCUETIME_API_KEY", None)
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

    def test_spawn_emit_called_when_api_key_present(self):
        # Arrange: write an API key so resolve_api_key() returns truthy
        import rt_claude.config as config_mod
        config_mod.STATE_DIR.mkdir(parents=True, exist_ok=True)
        config_mod.API_KEY_PATH.write_text("fake-test-key")
        # Reload cli so it picks up the reloaded config_mod with the new key path
        import rt_claude.cli as cli_mod
        importlib.reload(cli_mod)
        self.cli = cli_mod

        payload = {"session_id": "s-spawn", "cwd": self._tmpdir.name}
        # Stub resolve_context so no subprocess.run/git is invoked during cmd_hook,
        # leaving subprocess.Popen free to be called only by _spawn_emit.
        fake_ctx = {"project": "testproject", "branch": "main"}
        with unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            with unittest.mock.patch("rt_claude.cli.resolve_context", return_value=fake_ctx):
                with unittest.mock.patch("subprocess.Popen") as mock_popen:
                    rc = self.cli.main(["hook", "--event", "SessionStart"])

        self.assertEqual(rc, 0)
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]  # first positional arg (the command list)
        self.assertIn("_emit", call_args)
        self.assertIn("--desc", call_args)
        self.assertIn("--source", call_args)


if __name__ == "__main__":
    unittest.main()
