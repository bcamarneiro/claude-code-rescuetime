# Guided Setup Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an after-install onboarding nudge plus a `/rescuetime-setup` wizard that opens the RescueTime key page in the browser and saves the key for the user — backendless, stdlib-only, private by default.

**Architecture:** Two new CLI subcommands (`setup` opens the browser via stdlib `webbrowser`; `set-key` writes the key file at `0o600` with a hidden `getpass` prompt by default). A new `/rescuetime-setup` slash command drives the conversational flow. The existing one-time Windows notice is refactored into a unified, key-aware `_first_run_notice()` that nudges unconfigured users (once) via `systemMessage`.

**Tech Stack:** Python 3.9+ standard library only (`argparse`, `webbrowser`, `getpass`, `os`, `json`, `urllib`, `unittest`). No pip dependencies.

## Global Constraints

- **Python 3.9+, stdlib only.** No third-party packages. No `X | Y` union type syntax — use `typing.Optional`.
- **The `hook` command path always exits 0** — never raise/block a turn.
- **Privacy:** the default key-capture path keeps the key out of the chat/model/shell history (terminal `getpass`). Only repo name + branch + date is ever sent to RescueTime.
- **Key storage:** `~/.claude/rescuetime/api_key`, written `0o600` (best-effort on Windows), never committed.
- **Cross-platform:** `webbrowser.open` (works on macOS/Linux/Windows); hooks already use `python3 … || python …`.
- **Test runner:** `python3 -m unittest discover -s tests -v` (no pytest).
- **Version bump to 0.3.0** in `rt_claude/__init__.py`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.

---

### Task 1: `set-key` subcommand + `write_api_key` helper

**Files:**
- Modify: `rt_claude/config.py` (add `write_api_key`)
- Modify: `rt_claude/cli.py` (add `set-key` subparser, `cmd_set_key`, dispatch entry)
- Test: `tests/test_set_key.py`

**Interfaces:**
- Consumes: `config.API_KEY_PATH`, `config.resolve_api_key`, `client.post_highlight`.
- Produces: `config.write_api_key(key: str, key_path: Path = API_KEY_PATH) -> None` (creates parent dir, writes the stripped key at mode `0o600`). `cli.cmd_set_key(args) -> int` (reads key from `args.key` → else TTY `getpass` → else stdin; rejects empty → 1; saves; attempts a verification post; returns 0 on save).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_set_key.py
import os
import sys
import io
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import rt_claude.config as cfgmod
import rt_claude.cli as cli


class TestWriteApiKey(unittest.TestCase):
    def test_writes_stripped_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "api_key"
            cfgmod.write_api_key("  abc123  ", p)
            self.assertEqual(p.read_text(), "abc123")

    @unittest.skipIf(sys.platform == "win32", "POSIX permission check")
    def test_file_mode_is_600(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "api_key"
            cfgmod.write_api_key("k", p)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)


class TestCmdSetKey(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cfgmod.API_KEY_PATH
        cfgmod.API_KEY_PATH = Path(self._tmp.name) / "api_key"

    def tearDown(self):
        cfgmod.API_KEY_PATH = self._orig
        self._tmp.cleanup()

    def test_arg_key_saved_and_verified(self):
        args = mock.Mock(key="tok123")
        with mock.patch.object(cli, "post_highlight", return_value=200) as ph:
            rc = cli.cmd_set_key(args)
        self.assertEqual(rc, 0)
        self.assertEqual(cfgmod.API_KEY_PATH.read_text(), "tok123")
        ph.assert_called_once()

    def test_empty_key_rejected(self):
        args = mock.Mock(key="   ")
        rc = cli.cmd_set_key(args)
        self.assertEqual(rc, 1)
        self.assertFalse(cfgmod.API_KEY_PATH.exists())

    def test_save_succeeds_even_if_verify_fails(self):
        args = mock.Mock(key="tok")
        with mock.patch.object(cli, "post_highlight", side_effect=RuntimeError("net")):
            rc = cli.cmd_set_key(args)
        self.assertEqual(rc, 0)
        self.assertEqual(cfgmod.API_KEY_PATH.read_text(), "tok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_set_key -v`
Expected: FAIL — `module 'rt_claude.config' has no attribute 'write_api_key'`.

- [ ] **Step 3: Write minimal implementation**

Add to `rt_claude/config.py`:

```python
def write_api_key(key, key_path: Path = API_KEY_PATH) -> None:
    key_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key.strip().encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(str(key_path), 0o600)
    except OSError:
        pass  # best-effort on Windows
```

Add to `rt_claude/cli.py` (the `set-key` subparser inside `_build_parser`, before `return p`):

```python
    sk = sub.add_parser("set-key", help="Save your RescueTime API key")
    sk.add_argument("key", nargs="?", default=None)
```

Add the command function in `rt_claude/cli.py`:

```python
def _read_key(args):
    if getattr(args, "key", None):
        return args.key
    stdin = sys.stdin
    if stdin is not None and stdin.isatty():
        import getpass
        return getpass.getpass("RescueTime API key: ")
    return stdin.read() if stdin is not None else ""


def cmd_set_key(args) -> int:
    key = (_read_key(args) or "").strip()
    if not key:
        print("No key provided. Usage: rt-claude set-key <KEY>  (or pipe it on stdin)")
        return 1
    cfgmod.write_api_key(key)
    print("Saved key to {}".format(cfgmod.API_KEY_PATH))
    try:
        status = post_highlight(key, "rt-claude setup test", "claude-code")
        print("Verified — test highlight posted (HTTP {}).".format(status))
    except Exception as e:
        print("Saved, but the test post failed ({}). Double-check the key.".format(e))
    return 0
```

Wire into `main`'s dispatch dict (add the entry):

```python
        "set-key": cmd_set_key,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_set_key -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/config.py rt_claude/cli.py tests/test_set_key.py
git commit -m "feat: set-key subcommand + write_api_key (0600)"
```

---

### Task 2: `setup` subcommand (opens browser to the key page)

**Files:**
- Modify: `rt_claude/cli.py` (add `KEY_PAGE_URL`, `setup` subparser, `cmd_setup`, dispatch entry)
- Test: `tests/test_setup_cmd.py`

**Interfaces:**
- Produces: `cli.KEY_PAGE_URL = "https://www.rescuetime.com/anapi/manage"`. `cli.cmd_setup(args) -> int` — opens the key page via `webbrowser.open`, prints the private (terminal `set-key`) and convenient (chat-paste) finish paths; returns 0 even if the browser can't open.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_cmd.py
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
        self.assertIn(cli.KEY_PAGE_URL, text) or self.assertIn("browser", text.lower())

    def test_returns_0_when_browser_fails(self):
        with mock.patch("webbrowser.open", side_effect=RuntimeError("no display")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = cli.cmd_setup(mock.Mock())
        self.assertEqual(rc, 0)
        self.assertIn(cli.KEY_PAGE_URL, out.getvalue())  # printed for manual visit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_setup_cmd -v`
Expected: FAIL — `module 'rt_claude.cli' has no attribute 'cmd_setup'`.

- [ ] **Step 3: Write minimal implementation**

Add to `rt_claude/cli.py` (constant near `ISSUE_URL`):

```python
KEY_PAGE_URL = "https://www.rescuetime.com/anapi/manage"
```

Add the `setup` subparser inside `_build_parser` (before `return p`):

```python
    sub.add_parser("setup", help="Open the RescueTime key page and explain how to save your key")
```

Add the command function:

```python
def cmd_setup(args) -> int:
    import webbrowser
    try:
        opened = bool(webbrowser.open(KEY_PAGE_URL))
    except Exception:
        opened = False
    if opened:
        print("Opened your browser to the RescueTime API-key page.")
    print("Get your key at: {}".format(KEY_PAGE_URL))
    shim = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rt-claude")
    print("")
    print("Then finish one of two ways:")
    print("  1) Private (recommended) — in your OWN terminal, run:")
    print("       {} {} set-key".format(sys.executable, shim))
    print("     and paste your key at the hidden prompt.")
    print("  2) Convenient — paste the key into this chat and it will be saved for you.")
    return 0
```

Wire into `main`'s dispatch dict:

```python
        "setup": cmd_setup,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_setup_cmd -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/cli.py tests/test_setup_cmd.py
git commit -m "feat: setup subcommand opens the RescueTime key page"
```

---

### Task 3: Unified, key-aware first-run notice

**Files:**
- Modify: `rt_claude/cli.py` (replace `_windows_first_run_notice` with `_first_run_notice`; update `cmd_hook`)
- Modify/replace: `tests/test_windows_notice.py` → `tests/test_first_run_notice.py`

**Interfaces:**
- Consumes: `config.STATE_DIR`, `config.resolve_api_key`, `ISSUE_URL`.
- Produces: `cli._first_run_notice(platform=None) -> Optional[str]` — one-time (marker `STATE_DIR/first-run-notice-shown`) message. Includes a "run /rescuetime-setup" line when `resolve_api_key()` is falsy, and the Windows caveat line when `platform == "win32"`. Returns `None` (and writes no marker) when neither applies. `cmd_hook` emits it as `{"systemMessage": ...}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_first_run_notice.py
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import rt_claude.config as cfgmod
import rt_claude.cli as cli


class TestFirstRunNotice(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = cfgmod.STATE_DIR
        cfgmod.STATE_DIR = Path(self._tmp.name) / "rescuetime"

    def tearDown(self):
        cfgmod.STATE_DIR = self._orig
        self._tmp.cleanup()

    def test_no_key_nonwindows_nudges_setup(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value=None):
            msg = cli._first_run_notice("linux")
        self.assertIsNotNone(msg)
        self.assertIn("/rescuetime-setup", msg)
        self.assertNotIn(cli.ISSUE_URL, msg)

    def test_no_key_windows_has_both(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value=None):
            msg = cli._first_run_notice("win32")
        self.assertIn("/rescuetime-setup", msg)
        self.assertIn(cli.ISSUE_URL, msg)

    def test_key_present_nonwindows_is_none(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value="k"):
            self.assertIsNone(cli._first_run_notice("linux"))
        # No marker written → can still fire later
        self.assertFalse((cfgmod.STATE_DIR / "first-run-notice-shown").exists())

    def test_key_present_windows_shows_caveat_only(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value="k"):
            msg = cli._first_run_notice("win32")
        self.assertIn(cli.ISSUE_URL, msg)
        self.assertNotIn("/rescuetime-setup", msg)

    def test_fires_once(self):
        with mock.patch.object(cfgmod, "resolve_api_key", return_value=None):
            self.assertIsNotNone(cli._first_run_notice("win32"))
            self.assertIsNone(cli._first_run_notice("win32"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_first_run_notice -v`
Expected: FAIL — `module 'rt_claude.cli' has no attribute '_first_run_notice'`.

- [ ] **Step 3: Write minimal implementation**

In `rt_claude/cli.py`, delete `_windows_first_run_notice` and add:

```python
SETUP_NUDGE = "claude-code-rescuetime is installed but not connected — run /rescuetime-setup to link your RescueTime account."


def _first_run_notice(platform=None):
    """One-time notice: nudge unconfigured users to /rescuetime-setup, and warn
    Windows users it's unverified. Fires once via a marker; emits nothing (and
    writes no marker) when neither condition applies."""
    platform = sys.platform if platform is None else platform
    marker = cfgmod.STATE_DIR / "first-run-notice-shown"
    try:
        if marker.exists():
            return None
    except OSError:
        return None
    lines = []
    if not cfgmod.resolve_api_key():
        lines.append(SETUP_NUDGE)
    if platform == "win32":
        lines.append(
            "You're on Windows, where this plugin is best-effort and not yet "
            "verified by the maintainer — please report at " + ISSUE_URL
        )
    if not lines:
        return None
    try:
        cfgmod.STATE_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text("shown")
    except OSError:
        return None
    return "[claude-code-rescuetime] " + " ".join(lines)
```

In `cmd_hook`, replace the notice call:

```python
        notice = _first_run_notice()
        if notice:
            # systemMessage is surfaced to the user by Claude Code without
            # polluting the model context.
            print(json.dumps({"systemMessage": notice}))
```

Delete `tests/test_windows_notice.py` (replaced by `tests/test_first_run_notice.py`):

```bash
git rm tests/test_windows_notice.py
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (new first-run tests pass; whole suite green; no reference to the deleted function remains)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/cli.py tests/test_first_run_notice.py
git rm tests/test_windows_notice.py
git commit -m "feat: unify first-run notice — setup nudge for unconfigured users + Windows caveat"
```

---

### Task 4: `/rescuetime-setup` command, README, version bump to 0.3.0

**Files:**
- Create: `commands/rescuetime-setup.md`
- Modify: `README.md`
- Modify: `rt_claude/__init__.py`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:** none (command + docs + version).

- [ ] **Step 1: Create the slash command**

```markdown
<!-- commands/rescuetime-setup.md -->
---
description: Connect your RescueTime account — opens the API-key page and saves your key
allowed-tools: Bash(python3:*), Bash(python:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/rt-claude" setup || python "${CLAUDE_PLUGIN_ROOT}/rt-claude" setup`

The command above opened the RescueTime API-key page in the browser and printed two ways to finish. Guide the user:

- **Recommend the private path:** have them run the printed `set-key` command in their *own* terminal and paste the key at the hidden prompt — this keeps the key out of this chat entirely.
- **If they paste the key here instead:** save it for them by running `python3 "${CLAUDE_PLUGIN_ROOT}/rt-claude" set-key "<the key they pasted>"` (fall back to `python` if `python3` is missing), then report whether the verification highlight posted. Note that pasting here means the key passed through this conversation.
```

- [ ] **Step 2: Update the README**

In `README.md`, under the plugin-install section, replace the "verify it works" block with a setup-first flow:

```markdown
### First-time setup

After installing, run:

​```text
/rescuetime-setup
​```

It opens the RescueTime API-key page and saves your key — privately if you use the printed terminal command, or conveniently if you paste the key into the chat. On a fresh install you'll also be nudged to run it. To check or re-test later: `/rescuetime-status` and `/rescuetime-test`.
```

- [ ] **Step 3: Bump version to 0.3.0**

`rt_claude/__init__.py`:
```python
__version__ = "0.3.0"
```
`.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: change `"version": "0.2.1"` → `"version": "0.3.0"`.

- [ ] **Step 4: Run the full suite + JSON check**

Run:
```bash
python3 -m unittest discover -s tests -v
for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json hooks/hooks.json; do python3 -m json.tool "$f" >/dev/null && echo "OK $f"; done
```
Expected: all tests PASS; all JSON OK.

- [ ] **Step 5: Commit**

```bash
git add commands/rescuetime-setup.md README.md rt_claude/__init__.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat: /rescuetime-setup wizard + README; bump to 0.3.0"
```

---

## Self-Review

**Spec coverage:**
- After-install nudge (first-run, key-aware) → Task 3. ✓
- `rt-claude setup` opens browser + prints both paths → Task 2. ✓
- `rt-claude set-key` (arg/getpass/stdin, 0600, verify) → Task 1. ✓
- `/rescuetime-setup` command, private-default + chat fallback → Task 4. ✓
- Privacy (terminal default keeps key out of model) → Task 2 prints terminal cmd; Task 4 recommends it. ✓
- Cross-platform `webbrowser`, `python3||python` in command → Tasks 2, 4. ✓
- Version bump 0.3.0 → Task 4. ✓
- Migrate the Windows-notice test → Task 3. ✓

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `write_api_key(key, key_path)` defined in Task 1 and used by `cmd_set_key`; `cmd_setup`/`cmd_set_key`/`_first_run_notice`/`KEY_PAGE_URL`/`SETUP_NUDGE` names are consistent across tasks and the dispatch dict. `post_highlight` is the existing client function, patched by name in tests.

**One note:** Task 1's `cmd_set_key` and Task 2's `cmd_setup` both add a dispatch entry to the same `main` dict — when implementing in order, add each entry without removing the other's.
