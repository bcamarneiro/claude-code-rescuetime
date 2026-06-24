import json
import os
import tempfile
import unittest
from pathlib import Path


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _load_config(self, path=None):
        from rt_claude.config import load_config, DEFAULT_CONFIG
        return load_config(path), DEFAULT_CONFIG

    def test_defaults_when_no_file(self):
        cfg, defaults = self._load_config(self.tmp / "nope.json")
        self.assertEqual(cfg, defaults)

    def test_file_overrides_merge(self):
        from rt_claude.config import load_config, DEFAULT_CONFIG
        cfg_file = self.tmp / "config.json"
        cfg_file.write_text(json.dumps({"heartbeat_minutes": 15}))
        result = load_config(cfg_file)
        expected = dict(DEFAULT_CONFIG)
        expected["heartbeat_minutes"] = 15
        self.assertEqual(result, expected)

    def test_corrupt_file_falls_back(self):
        from rt_claude.config import load_config, DEFAULT_CONFIG
        cfg_file = self.tmp / "config.json"
        cfg_file.write_text("{not json")
        result = load_config(cfg_file)
        self.assertEqual(result, DEFAULT_CONFIG)

    def test_key_env_wins(self):
        from rt_claude.config import resolve_api_key
        key_file = self.tmp / "api_key"
        key_file.write_text("file-key")
        env = {"RESCUETIME_API_KEY": "env-key"}
        result = resolve_api_key(env=env, key_path=key_file)
        self.assertEqual(result, "env-key")

    def test_key_from_file_when_no_env(self):
        from rt_claude.config import resolve_api_key
        key_file = self.tmp / "api_key"
        key_file.write_text("  file-key  \n")
        result = resolve_api_key(env={}, key_path=key_file)
        self.assertEqual(result, "file-key")

    def test_key_absent_is_none(self):
        from rt_claude.config import resolve_api_key
        result = resolve_api_key(env={}, key_path=self.tmp / "no_key")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
