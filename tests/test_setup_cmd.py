import io
import unittest
import contextlib
from unittest import mock

import rt_claude.cli as cli


class TestCmdSetup(unittest.TestCase):
    def test_opens_key_page_and_prints_paths(self):
        with mock.patch("webbrowser.open", return_value=True) as wb:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = cli.cmd_setup(mock.Mock())
        self.assertEqual(rc, 0)
        wb.assert_called_once_with(cli.KEY_PAGE_URL)
        text = out.getvalue()
        self.assertIn("set-key", text)        # private path mentioned
        self.assertIn(cli.KEY_PAGE_URL, text)

    def test_returns_0_when_browser_fails(self):
        with mock.patch("webbrowser.open", side_effect=RuntimeError("no display")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = cli.cmd_setup(mock.Mock())
        self.assertEqual(rc, 0)
        self.assertIn(cli.KEY_PAGE_URL, out.getvalue())  # printed for manual visit
