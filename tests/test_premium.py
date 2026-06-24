import contextlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import rt_claude.cli as cli
import rt_claude.config as cfgmod
from rt_claude.client import PremiumRequiredError, post_highlight


def _http_error(code, body):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(body.encode()))


class TestPremiumDetection(unittest.TestCase):
    def test_premium_400_raises_premium_error(self):
        def opener(req, timeout=None):
            raise _http_error(
                400,
                '{"error":"# premium feature","messages":"Daily highlights are a premium feature."}',
            )
        with self.assertRaises(PremiumRequiredError):
            post_highlight("k", "d", "s", today="2026-06-24", opener=opener)

    def test_non_premium_400_reraises_httperror(self):
        def opener(req, timeout=None):
            raise _http_error(400, '{"error":"some other problem"}')
        with self.assertRaises(urllib.error.HTTPError):
            post_highlight("k", "d", "s", today="2026-06-24", opener=opener)


class TestSetKeyPremiumMessage(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cfgmod.API_KEY_PATH
        cfgmod.API_KEY_PATH = Path(self._tmp.name) / "api_key"

    def tearDown(self):
        cfgmod.API_KEY_PATH = self._orig
        self._tmp.cleanup()

    def test_set_key_premium_saves_and_explains(self):
        with mock.patch.object(cli, "post_highlight", side_effect=PremiumRequiredError("x")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = cli.cmd_set_key(mock.Mock(key="tok"))
        self.assertEqual(rc, 0)  # key still saved
        self.assertIn("Premium", out.getvalue())
        self.assertNotIn("Double-check the key", out.getvalue())
        self.assertEqual(cfgmod.API_KEY_PATH.read_text(), "tok")


if __name__ == "__main__":
    unittest.main()
