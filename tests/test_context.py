import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestContext(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_outside_git(self):
        from rt_claude.context import resolve_context
        result = resolve_context(self.tmp)
        self.assertEqual(result["project"], Path(self.tmp).name)
        self.assertIsNone(result["branch"])

    def test_inside_git(self):
        from rt_claude.context import resolve_context
        repo = os.path.join(self.tmp, "myrepo")
        os.makedirs(repo)
        subprocess.run(["git", "init", repo], capture_output=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "test@test.com"], capture_output=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "Test"], capture_output=True)
        # Create initial commit so we can checkout a branch
        test_file = os.path.join(repo, "README.md")
        Path(test_file).write_text("hello")
        subprocess.run(["git", "-C", repo, "add", "."], capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-m", "init"], capture_output=True)
        subprocess.run(["git", "-C", repo, "checkout", "-b", "feature-x"], capture_output=True)
        result = resolve_context(repo)
        self.assertEqual(result["project"], "myrepo")
        self.assertEqual(result["branch"], "feature-x")


if __name__ == "__main__":
    unittest.main()
