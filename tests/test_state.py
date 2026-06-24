import json
import tempfile
import unittest
from pathlib import Path


class TestState(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_round_trip(self):
        from rt_claude.state import save_session, load_session
        data = {"last_context": "myproject@main", "last_emit_at": 123456.0}
        save_session("sess1", data, self.base)
        result = load_session("sess1", self.base)
        self.assertEqual(result, data)

    def test_missing_is_empty(self):
        from rt_claude.state import load_session
        result = load_session("nonexistent", self.base)
        self.assertEqual(result, {})

    def test_corrupt_is_empty(self):
        from rt_claude.state import load_session
        (self.base / "corrupt.json").write_text("{bad json")
        result = load_session("corrupt", self.base)
        self.assertEqual(result, {})

    def test_clear(self):
        from rt_claude.state import save_session, load_session, clear_session
        save_session("to_clear", {"key": "val"}, self.base)
        clear_session("to_clear", self.base)
        result = load_session("to_clear", self.base)
        self.assertEqual(result, {})

    def test_session_id_sanitized(self):
        from rt_claude.state import save_session, load_session
        # Session IDs with special chars get sanitized
        data = {"x": 1}
        save_session("sess/../evil", data, self.base)
        # Should still be loadable under sanitized name
        result = load_session("sess/../evil", self.base)
        self.assertEqual(result, data)


if __name__ == "__main__":
    unittest.main()
