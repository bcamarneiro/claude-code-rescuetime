import unittest

from rt_claude.cli import _detach_kwargs


class TestDetachKwargs(unittest.TestCase):
    def test_posix_uses_new_session(self):
        self.assertEqual(_detach_kwargs("linux"), {"start_new_session": True})
        self.assertEqual(_detach_kwargs("darwin"), {"start_new_session": True})

    def test_windows_uses_creationflags(self):
        kw = _detach_kwargs("win32")
        self.assertIn("creationflags", kw)
        self.assertNotIn("start_new_session", kw)
        # DETACHED_PROCESS (0x8) | CREATE_NEW_PROCESS_GROUP (0x200)
        self.assertGreaterEqual(kw["creationflags"], 0x8)


if __name__ == "__main__":
    unittest.main()
