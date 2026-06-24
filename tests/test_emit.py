import unittest
from rt_claude.emit import format_description, is_excluded, decide


class TestFormatDescription(unittest.TestCase):
    def test_with_branch(self):
        result = format_description("{project} · {branch}", "myproject", "main")
        self.assertEqual(result, "myproject · main")

    def test_without_branch(self):
        result = format_description("{project} · {branch}", "myproject", None)
        self.assertEqual(result, "myproject")

    def test_truncation_to_255(self):
        long_project = "p" * 300
        result = format_description("{project}", long_project, None)
        self.assertEqual(len(result), 255)


class TestIsExcluded(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(is_excluded("myproject", ["myproject", "other"]))

    def test_glob_match(self):
        self.assertTrue(is_excluded("test-project", ["test-*"]))

    def test_no_match(self):
        self.assertFalse(is_excluded("myproject", ["other", "different"]))


class TestDecide(unittest.TestCase):
    def _ctx(self, project="myproject", branch="main"):
        return {"project": project, "branch": branch}

    def _cfg(self, **kwargs):
        base = {
            "enabled": True,
            "exclude_projects": [],
            "heartbeat_minutes": 0,
            "source_label": "claude-code",
            "description_template": "{project} · {branch}",
        }
        base.update(kwargs)
        return base

    def test_disabled_config_returns_none(self):
        action, _ = decide("SessionStart", {}, self._ctx(), self._cfg(enabled=False), 1000.0)
        self.assertIsNone(action)

    def test_excluded_project_returns_none(self):
        action, _ = decide("SessionStart", {}, self._ctx(), self._cfg(exclude_projects=["myproject"]), 1000.0)
        self.assertIsNone(action)

    def test_session_end_returns_none(self):
        action, _ = decide("SessionEnd", {}, self._ctx(), self._cfg(), 1000.0)
        self.assertIsNone(action)

    def test_new_context_emits(self):
        session = {}
        action, new_sess = decide("SessionStart", session, self._ctx(), self._cfg(), 1000.0)
        self.assertIsNotNone(action)
        self.assertEqual(action["description"], "myproject · main")
        self.assertEqual(action["source"], "claude-code")
        self.assertEqual(new_sess["last_context"], "myproject@main")

    def test_same_context_no_heartbeat_no_emit(self):
        session = {"last_context": "myproject@main", "last_emit_at": 900.0}
        action, _ = decide("UserPromptSubmit", session, self._ctx(), self._cfg(heartbeat_minutes=0), 1000.0)
        self.assertIsNone(action)

    def test_same_context_with_heartbeat_after_enough_time_emits(self):
        # heartbeat = 5 min = 300s, elapsed = 400s → should emit
        session = {"last_context": "myproject@main", "last_emit_at": 600.0}
        action, _ = decide("UserPromptSubmit", session, self._ctx(), self._cfg(heartbeat_minutes=5), 1000.0)
        self.assertIsNotNone(action)

    def test_same_context_heartbeat_too_soon_no_emit(self):
        # heartbeat = 5 min = 300s, elapsed = 50s → should NOT emit
        session = {"last_context": "myproject@main", "last_emit_at": 950.0}
        action, _ = decide("UserPromptSubmit", session, self._ctx(), self._cfg(heartbeat_minutes=5), 1000.0)
        self.assertIsNone(action)

    def test_same_context_heartbeat_minutes_zero_no_emit(self):
        session = {"last_context": "myproject@main", "last_emit_at": 0.0}
        action, _ = decide("UserPromptSubmit", session, self._ctx(), self._cfg(heartbeat_minutes=0), 1000.0)
        self.assertIsNone(action)

    def test_session_start_always_emits_new_context(self):
        session = {}
        action, new_sess = decide("SessionStart", session, self._ctx(), self._cfg(), 1000.0)
        self.assertIsNotNone(action)

    def test_new_session_state_updated(self):
        action, new_sess = decide("SessionStart", {}, self._ctx(), self._cfg(), 1000.0)
        self.assertEqual(new_sess["project"], "myproject")
        self.assertEqual(new_sess["branch"], "main")
        self.assertEqual(new_sess["last_activity_at"], 1000.0)

    def test_context_change_emits(self):
        session = {"last_context": "myproject@main", "last_emit_at": 999.0}
        action, new_sess = decide("UserPromptSubmit", session, self._ctx(branch="feature"), self._cfg(), 1000.0)
        self.assertIsNotNone(action)
        self.assertEqual(new_sess["last_context"], "myproject@feature")

    def test_format_description_no_branch(self):
        action, _ = decide("SessionStart", {}, self._ctx(branch=None), self._cfg(), 1000.0)
        self.assertIsNotNone(action)
        self.assertNotIn("None", action["description"])

    def test_no_git_branch_emits_once_and_deduplicates(self):
        # Non-git context: branch=None
        # First call (SessionStart) should emit
        action, new_sess = decide("SessionStart", {}, self._ctx(branch=None), self._cfg(), 1000.0)
        self.assertIsNotNone(action)
        # context_key must not contain the literal string "None"
        self.assertNotIn("None", new_sess["last_context"])
        # Second call (Stop) with the same None branch using the session from above should NOT emit
        action2, _ = decide("Stop", new_sess, self._ctx(branch=None), self._cfg(), 1001.0)
        self.assertIsNone(action2)


if __name__ == "__main__":
    unittest.main()
