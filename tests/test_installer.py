import sys
import unittest


class TestInstaller(unittest.TestCase):
    def test_install_adds_all_events_idempotently(self):
        from rt_claude.installer import install_hooks, HOOK_EVENTS
        settings = {}
        settings = install_hooks(settings, "/path/to/rt-claude", python="/usr/bin/python3")
        # Install twice to verify idempotency
        settings = install_hooks(settings, "/path/to/rt-claude", python="/usr/bin/python3")
        for event in HOOK_EVENTS:
            entries = settings["hooks"][event]
            rt_entries = [e for e in entries if e.get("_rt_claude")]
            self.assertEqual(len(rt_entries), 1, msg="Expected exactly 1 rt_claude entry for event {}".format(event))

    def test_uninstall_removes_only_ours(self):
        from rt_claude.installer import install_hooks, uninstall_hooks, HOOK_EVENTS
        # Start with a non-rt-claude entry
        settings = {
            "hooks": {
                "SessionStart": [{"type": "command", "command": "other-tool hook"}],
            }
        }
        settings = install_hooks(settings, "/path/to/rt-claude", python="/usr/bin/python3")
        settings = uninstall_hooks(settings)
        # No _rt_claude entries should remain
        for event, entries in settings["hooks"].items():
            for entry in entries:
                self.assertFalse(entry.get("_rt_claude"), msg="Found _rt_claude entry after uninstall")
        # The non-rt entry should still be there
        self.assertTrue(
            any(e.get("command") == "other-tool hook" for e in settings["hooks"].get("SessionStart", [])),
            msg="Non-rt-claude entry was removed during uninstall"
        )

    def test_command_format(self):
        from rt_claude.installer import hook_command
        cmd = hook_command("/path/to/rt-claude", "SessionStart", python="/usr/bin/python3")
        self.assertIn("/usr/bin/python3", cmd)
        self.assertIn("/path/to/rt-claude", cmd)
        self.assertIn("SessionStart", cmd)


if __name__ == "__main__":
    unittest.main()
