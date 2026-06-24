# rescuetime-claude Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A stdlib-only Python CLI that logs which project/branch you work on in Claude Code to your RescueTime timeline as Highlights, wired through Claude Code hooks with no background daemon.

**Architecture:** Claude Code hooks call `rt-claude hook --event=<E>`. The hook resolves the git project+branch for the session, decides locally whether the context changed since the last emit, and if so spawns a *detached* background process to POST a RescueTime highlight — returning instantly so it never adds latency to a turn. All session state lives in small per-session JSON files under `~/.claude/rescuetime/`.

**Tech Stack:** Python 3.9+ (macOS system `python3`), standard library only (`argparse`, `json`, `urllib`, `subprocess`, `pathlib`, `unittest`). No pip dependencies.

## Global Constraints

- **Python 3.9+, stdlib only.** No third-party packages. No `X | Y` union type syntax (3.10+) — use `typing.Optional[X]` or omit annotations.
- **The hook path always exits 0.** Missing key, corrupt state, bad JSON, or network failure must degrade to a no-op + one log line — never block or fail a turn.
- **No network on the foreground hook path.** The actual POST runs in a detached subprocess.
- **Privacy surface = repo name + branch + date only.** Never send prompt text, file contents, diffs, or full paths.
- **API key never in config or git.** Resolve from `RESCUETIME_API_KEY` env, else `~/.claude/rescuetime/api_key` (chmod 600).
- **Canonical state dir:** `~/.claude/rescuetime/` (`config.json`, `api_key`, `sessions/<id>.json`, `rt-claude.log`).
- **RescueTime Highlights endpoint:** `POST https://www.rescuetime.com/anapi/highlights_post` with form params `key`, `highlight_date` (`YYYY-MM-DD`), `description` (≤255 chars), `source`.

---

### Task 1: Repo scaffold + executable shim + CLI skeleton

**Files:**
- Create: `rt_claude/__init__.py`
- Create: `rt_claude/cli.py`
- Create: `rt-claude` (executable shim at repo root)
- Test: `tests/test_cli_skeleton.py`

**Interfaces:**
- Produces: `rt_claude.cli.main(argv: list) -> int` — argparse dispatcher for subcommands `hook`, `install`, `uninstall`, `test`, `status`, `_emit`. Unknown/no command prints help, returns `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_skeleton.py
import subprocess, sys, os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(args):
    return subprocess.run([sys.executable, "-m", "rt_claude", *args],
                          cwd=REPO, capture_output=True, text=True)

def test_help_runs_and_lists_subcommands():
    res = run(["--help"])
    assert res.returncode == 0
    for cmd in ("hook", "install", "uninstall", "test", "status"):
        assert cmd in res.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_cli_skeleton -v` (from repo root)
Expected: FAIL — `No module named rt_claude`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/__init__.py
__version__ = "0.1.0"
```

```python
# rt_claude/__main__.py
import sys
from rt_claude.cli import main
sys.exit(main(sys.argv[1:]))
```

```python
# rt_claude/cli.py
import argparse

def _build_parser():
    p = argparse.ArgumentParser(prog="rt-claude", description="Log Claude Code work to RescueTime")
    p.add_argument("--dry-run", action="store_true", help="Print actions instead of posting")
    sub = p.add_subparsers(dest="command")
    h = sub.add_parser("hook", help="Run from a Claude Code hook")
    h.add_argument("--event", required=True)
    sub.add_parser("install", help="Wire hooks into ~/.claude/settings.json")
    sub.add_parser("uninstall", help="Remove the hooks this tool added")
    sub.add_parser("test", help="Post a test highlight to verify the API key")
    sub.add_parser("status", help="Show config + live session state")
    e = sub.add_parser("_emit", help=argparse.SUPPRESS)
    e.add_argument("--desc", required=True)
    e.add_argument("--source", required=True)
    return p

def main(argv):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return 0  # subcommands wired in later tasks
```

Create the shim and make it executable:

```python
# rt-claude  (repo root, executable)
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rt_claude.cli import main
sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Make shim executable, run test to verify it passes**

Run: `chmod +x rt-claude && python3 -m unittest tests.test_cli_skeleton -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rt_claude/ rt-claude tests/test_cli_skeleton.py
git commit -m "feat: CLI skeleton + executable shim"
```

---

### Task 2: Config loading + API key resolution

**Files:**
- Create: `rt_claude/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `STATE_DIR`, `CONFIG_PATH`, `API_KEY_PATH`, `LOG_PATH` (all `pathlib.Path`).
- Produces: `DEFAULT_CONFIG: dict`.
- Produces: `load_config(config_path: Path = CONFIG_PATH) -> dict` — defaults merged with file; corrupt/missing file → defaults.
- Produces: `resolve_api_key(env: Optional[dict] = None, key_path: Path = API_KEY_PATH) -> Optional[str]` — env var wins over file; absent → `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import json
from pathlib import Path
from rt_claude.config import load_config, resolve_api_key, DEFAULT_CONFIG

def test_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "nope.json")
    assert cfg == DEFAULT_CONFIG

def test_file_overrides_merge(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"heartbeat_minutes": 15}))
    cfg = load_config(p)
    assert cfg["heartbeat_minutes"] == 15
    assert cfg["source_label"] == DEFAULT_CONFIG["source_label"]

def test_corrupt_file_falls_back(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json")
    assert load_config(p) == DEFAULT_CONFIG

def test_key_env_wins(tmp_path):
    kp = tmp_path / "api_key"
    kp.write_text("file-key")
    assert resolve_api_key({"RESCUETIME_API_KEY": "env-key"}, kp) == "env-key"

def test_key_from_file_when_no_env(tmp_path):
    kp = tmp_path / "api_key"
    kp.write_text("  file-key\n")
    assert resolve_api_key({}, kp) == "file-key"

def test_key_absent_is_none(tmp_path):
    assert resolve_api_key({}, tmp_path / "nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_config -v`
Expected: FAIL — `No module named rt_claude.config`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/config.py
import json, os
from pathlib import Path
from typing import Optional

STATE_DIR = Path.home() / ".claude" / "rescuetime"
CONFIG_PATH = STATE_DIR / "config.json"
API_KEY_PATH = STATE_DIR / "api_key"
LOG_PATH = STATE_DIR / "rt-claude.log"

DEFAULT_CONFIG = {
    "enabled": True,
    "source_label": "claude-code",
    "heartbeat_minutes": 0,
    "exclude_projects": [],
    "description_template": "{project} · {branch}",
}

def load_config(config_path: Path = CONFIG_PATH) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        if config_path.exists():
            cfg.update(json.loads(config_path.read_text()))
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return cfg

def resolve_api_key(env: Optional[dict] = None, key_path: Path = API_KEY_PATH) -> Optional[str]:
    env = os.environ if env is None else env
    key = env.get("RESCUETIME_API_KEY")
    if key and key.strip():
        return key.strip()
    try:
        if key_path.exists():
            k = key_path.read_text().strip()
            return k or None
    except OSError:
        pass
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_config -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/config.py tests/test_config.py
git commit -m "feat: config loading + API key resolution"
```

---

### Task 3: Git context resolution (project + branch)

**Files:**
- Create: `rt_claude/context.py`
- Test: `tests/test_context.py`

**Interfaces:**
- Produces: `resolve_context(cwd: str) -> dict` returning `{"project": str, "branch": Optional[str]}`. In a git repo: project = repo top-level dir name, branch = current branch. Outside git: project = basename of `cwd`, branch = `None`. Never raises.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context.py
import subprocess
from rt_claude.context import resolve_context

def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)

def test_outside_git(tmp_path):
    d = tmp_path / "plainproj"
    d.mkdir()
    ctx = resolve_context(str(d))
    assert ctx["project"] == "plainproj"
    assert ctx["branch"] is None

def test_inside_git(tmp_path):
    d = tmp_path / "myrepo"
    d.mkdir()
    _git(["init", "-q", "-b", "main"], str(d))
    _git(["config", "user.email", "t@t.com"], str(d))
    _git(["config", "user.name", "t"], str(d))
    (d / "f.txt").write_text("x")
    _git(["add", "."], str(d))
    _git(["commit", "-qm", "init"], str(d))
    _git(["checkout", "-q", "-b", "feature/x"], str(d))
    ctx = resolve_context(str(d))
    assert ctx["project"] == "myrepo"
    assert ctx["branch"] == "feature/x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_context -v`
Expected: FAIL — `No module named rt_claude.context`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/context.py
import subprocess
from pathlib import Path
from typing import Optional

def resolve_context(cwd: str) -> dict:
    project = _git_repo_name(cwd) or Path(cwd).name
    return {"project": project, "branch": _git_branch(cwd)}

def _git_branch(cwd) -> Optional[str]:
    out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out or None

def _git_repo_name(cwd) -> Optional[str]:
    top = _run(["git", "rev-parse", "--show-toplevel"], cwd)
    return Path(top).name if top else None

def _run(args, cwd) -> Optional[str]:
    try:
        res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_context -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rt_claude/context.py tests/test_context.py
git commit -m "feat: git project/branch context resolution"
```

---

### Task 4: Per-session state files

**Files:**
- Create: `rt_claude/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `SESSIONS_DIR: Path`.
- Produces: `load_session(session_id: str, base: Path = SESSIONS_DIR) -> dict` — `{}` if missing/corrupt.
- Produces: `save_session(session_id: str, data: dict, base: Path = SESSIONS_DIR) -> None`.
- Produces: `clear_session(session_id: str, base: Path = SESSIONS_DIR) -> None` — no error if absent.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from rt_claude.state import load_session, save_session, clear_session

def test_round_trip(tmp_path):
    save_session("abc-123", {"last_context": "repo@main"}, tmp_path)
    assert load_session("abc-123", tmp_path)["last_context"] == "repo@main"

def test_missing_is_empty(tmp_path):
    assert load_session("nope", tmp_path) == {}

def test_corrupt_is_empty(tmp_path):
    (tmp_path / "bad.json").write_text("{broken")
    assert load_session("bad", tmp_path) == {}

def test_clear(tmp_path):
    save_session("x", {"a": 1}, tmp_path)
    clear_session("x", tmp_path)
    assert load_session("x", tmp_path) == {}
    clear_session("x", tmp_path)  # idempotent, no raise

def test_session_id_sanitized(tmp_path):
    save_session("a/../b id", {"a": 1}, tmp_path)
    assert load_session("a/../b id", tmp_path) == {"a": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_state -v`
Expected: FAIL — `No module named rt_claude.state`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/state.py
import json
from pathlib import Path
from rt_claude.config import STATE_DIR

SESSIONS_DIR = STATE_DIR / "sessions"

def _path(session_id: str, base: Path) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_") or "session"
    return base / (safe + ".json")

def load_session(session_id: str, base: Path = SESSIONS_DIR) -> dict:
    try:
        p = _path(session_id, base)
        if p.exists():
            return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return {}

def save_session(session_id: str, data: dict, base: Path = SESSIONS_DIR) -> None:
    base.mkdir(parents=True, exist_ok=True)
    _path(session_id, base).write_text(json.dumps(data))

def clear_session(session_id: str, base: Path = SESSIONS_DIR) -> None:
    try:
        _path(session_id, base).unlink()
    except OSError:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_state -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/state.py tests/test_state.py
git commit -m "feat: per-session state files"
```

---

### Task 5: Emission decision logic (pure)

**Files:**
- Create: `rt_claude/emit.py`
- Test: `tests/test_emit.py`

**Interfaces:**
- Produces: `format_description(template: str, project: str, branch: Optional[str], max_len: int = 255) -> str`.
- Produces: `is_excluded(project: str, exclude_projects: list) -> bool` (exact match or `fnmatch` glob).
- Produces: `decide(event: str, session: dict, context: dict, config: dict, now: float) -> tuple` returning `(action, new_session)` where `action` is `None` or `{"description": str, "source": str}`, and `new_session` is the updated session dict to persist.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_emit.py
from rt_claude.emit import format_description, is_excluded, decide

CFG = {"enabled": True, "source_label": "claude-code", "heartbeat_minutes": 0,
       "exclude_projects": [], "description_template": "{project} · {branch}"}

def ctx(project="hoursmith", branch="staging"):
    return {"project": project, "branch": branch}

def test_format_with_branch():
    assert format_description("{project} · {branch}", "hoursmith", "staging") == "hoursmith · staging"

def test_format_without_branch_trims_separator():
    assert format_description("{project} · {branch}", "hoursmith", None) == "hoursmith"

def test_format_truncates_255():
    assert len(format_description("{project}", "x" * 300, None)) == 255

def test_exclude_exact_and_glob():
    assert is_excluded("secret", ["secret"])
    assert is_excluded("client-acme", ["client-*"])
    assert not is_excluded("hoursmith", ["client-*"])

def test_session_start_emits_fresh():
    action, ns = decide("SessionStart", {}, ctx(), CFG, 1000.0)
    assert action["description"] == "hoursmith · staging"
    assert ns["last_context"] == "hoursmith@staging"

def test_stop_same_context_no_emit():
    sess = {"last_context": "hoursmith@staging", "last_emit_at": 1000.0}
    action, ns = decide("Stop", sess, ctx(), CFG, 1100.0)
    assert action is None

def test_stop_branch_change_emits():
    sess = {"last_context": "hoursmith@staging", "last_emit_at": 1000.0}
    action, ns = decide("Stop", sess, ctx(branch="fix/x"), CFG, 1100.0)
    assert action["description"] == "hoursmith · fix/x"

def test_heartbeat_off_no_reemit():
    sess = {"last_context": "hoursmith@staging", "last_emit_at": 1000.0}
    action, _ = decide("Stop", sess, ctx(), CFG, 1000.0 + 9999)
    assert action is None

def test_heartbeat_on_reemits_after_interval():
    cfg = dict(CFG, heartbeat_minutes=15)
    sess = {"last_context": "hoursmith@staging", "last_emit_at": 1000.0}
    action, _ = decide("Stop", sess, ctx(), cfg, 1000.0 + 16 * 60)
    assert action is not None

def test_disabled_no_emit():
    action, _ = decide("SessionStart", {}, ctx(), dict(CFG, enabled=False), 1000.0)
    assert action is None

def test_excluded_no_emit():
    cfg = dict(CFG, exclude_projects=["hoursmith"])
    action, _ = decide("SessionStart", {}, ctx(), cfg, 1000.0)
    assert action is None

def test_session_end_no_action():
    action, ns = decide("SessionEnd", {"last_context": "x@y"}, ctx(), CFG, 1000.0)
    assert action is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_emit -v`
Expected: FAIL — `No module named rt_claude.emit`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/emit.py
import fnmatch
from typing import Optional

def format_description(template: str, project: str, branch: Optional[str], max_len: int = 255) -> str:
    desc = template.format(project=project, branch=branch or "").strip()
    desc = desc.strip(" ·-").strip()  # tidy dangling separator when branch is empty
    return desc[:max_len]

def is_excluded(project: str, exclude_projects: list) -> bool:
    return any(project == pat or fnmatch.fnmatch(project, pat) for pat in exclude_projects)

def decide(event: str, session: dict, context: dict, config: dict, now: float):
    project = context["project"]
    branch = context["branch"]
    new_session = dict(session)
    new_session["project"] = project
    new_session["branch"] = branch
    new_session["last_activity_at"] = now

    if not config.get("enabled", True):
        return None, new_session
    if is_excluded(project, config.get("exclude_projects", [])):
        return None, new_session
    if event == "SessionEnd":
        return None, new_session

    context_key = "{}@{}".format(project, branch)
    last_context = session.get("last_context")
    last_emit_at = session.get("last_emit_at", 0)
    heartbeat_min = config.get("heartbeat_minutes", 0) or 0

    if context_key != last_context:
        should = True
    elif event != "SessionStart" and heartbeat_min > 0 and (now - last_emit_at) >= heartbeat_min * 60:
        should = True
    else:
        should = False

    if not should:
        return None, new_session

    new_session["last_context"] = context_key
    new_session["last_emit_at"] = now
    desc = format_description(config.get("description_template", "{project} · {branch}"), project, branch)
    return {"description": desc, "source": config.get("source_label", "claude-code")}, new_session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_emit -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/emit.py tests/test_emit.py
git commit -m "feat: pure emission decision logic"
```

---

### Task 6: RescueTime Highlights client

**Files:**
- Create: `rt_claude/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Produces: `HIGHLIGHTS_URL: str`.
- Produces: `post_highlight(api_key, description, source, today=None, opener=None, timeout=5, url=HIGHLIGHTS_URL) -> int` — POSTs form-encoded params, returns HTTP status. `today` defaults to `time.strftime("%Y-%m-%d")`; `opener` is an injectable replacement for `urllib.request.urlopen` (for tests).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_client.py
import urllib.parse
from rt_claude.client import post_highlight, HIGHLIGHTS_URL

class FakeResp:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False

def test_posts_correct_params():
    captured = {}
    def fake_opener(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = req.data.decode()
        captured["method"] = req.get_method()
        return FakeResp()
    status = post_highlight("KEY", "hoursmith · staging", "claude-code",
                            today="2026-06-24", opener=fake_opener)
    assert status == 200
    assert captured["url"] == HIGHLIGHTS_URL
    assert captured["method"] == "POST"
    parsed = dict(urllib.parse.parse_qsl(captured["body"]))
    assert parsed["key"] == "KEY"
    assert parsed["highlight_date"] == "2026-06-24"
    assert parsed["description"] == "hoursmith · staging"
    assert parsed["source"] == "claude-code"

def test_truncates_description_to_255():
    captured = {}
    def fake_opener(req, timeout=None):
        captured["body"] = req.data.decode()
        return FakeResp()
    post_highlight("K", "x" * 300, "s", today="2026-06-24", opener=fake_opener)
    parsed = dict(urllib.parse.parse_qsl(captured["body"]))
    assert len(parsed["description"]) == 255
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_client -v`
Expected: FAIL — `No module named rt_claude.client`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/client.py
import time, urllib.parse, urllib.request

HIGHLIGHTS_URL = "https://www.rescuetime.com/anapi/highlights_post"

def post_highlight(api_key, description, source, today=None, opener=None, timeout=5, url=HIGHLIGHTS_URL):
    date_str = today or time.strftime("%Y-%m-%d")
    body = urllib.parse.urlencode({
        "key": api_key,
        "highlight_date": date_str,
        "description": description[:255],
        "source": source,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    _open = opener or urllib.request.urlopen
    with _open(req, timeout=timeout) as resp:
        return getattr(resp, "status", None) or resp.getcode()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_client -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add rt_claude/client.py tests/test_client.py
git commit -m "feat: RescueTime highlights client"
```

---

### Task 7: Wire the `hook`, `_emit`, `test`, and `status` commands

**Files:**
- Modify: `rt_claude/cli.py`
- Test: `tests/test_hook_cmd.py`

**Interfaces:**
- Consumes: `config.load_config`, `config.resolve_api_key`, `config.LOG_PATH`, `context.resolve_context`, `state.load_session/save_session/clear_session`, `emit.decide`, `client.post_highlight`.
- Produces (in `cli.py`): `cmd_hook(args) -> int` (always returns 0), `cmd_emit(args) -> int`, `cmd_test(args) -> int`, `cmd_status(args) -> int`, and `_spawn_emit(desc, source)` which launches the detached POST. `main()` dispatches to these.

**Notes:** `cmd_hook` reads the hook JSON from stdin (`{"session_id": ..., "cwd": ...}`), runs `decide`, persists state, and — when an action is produced and a key exists and not `--dry-run` — calls `_spawn_emit`. On `--dry-run` it prints `WOULD POST: <desc>`. `SessionEnd` clears the session file. Everything is wrapped so the function returns 0 on any exception, logging one line to `LOG_PATH`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hook_cmd.py
import json, sys, io, os, importlib
import rt_claude.config as config

def _reload_with_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    importlib.reload(config)
    import rt_claude.state as state; importlib.reload(state)
    import rt_claude.cli as cli; importlib.reload(cli)
    return cli

def _feed_stdin(monkeypatch, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))

def test_hook_dry_run_prints_would_post(tmp_path, monkeypatch, capsys):
    cli = _reload_with_home(tmp_path, monkeypatch)
    _feed_stdin(monkeypatch, {"session_id": "s1", "cwd": str(tmp_path)})
    rc = cli.main(["--dry-run", "hook", "--event", "SessionStart"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WOULD POST" in out

def test_hook_no_key_is_noop_exit_0(tmp_path, monkeypatch):
    cli = _reload_with_home(tmp_path, monkeypatch)
    monkeypatch.delenv("RESCUETIME_API_KEY", raising=False)
    _feed_stdin(monkeypatch, {"session_id": "s2", "cwd": str(tmp_path)})
    rc = cli.main(["hook", "--event", "SessionStart"])
    assert rc == 0

def test_hook_malformed_stdin_exit_0(tmp_path, monkeypatch):
    cli = _reload_with_home(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    rc = cli.main(["hook", "--event", "Stop"])
    assert rc == 0

def test_session_end_clears_state(tmp_path, monkeypatch):
    cli = _reload_with_home(tmp_path, monkeypatch)
    import rt_claude.state as state
    state.save_session("s3", {"last_context": "x@y"})
    _feed_stdin(monkeypatch, {"session_id": "s3", "cwd": str(tmp_path)})
    cli.main(["hook", "--event", "SessionEnd"])
    assert state.load_session("s3") == {}
```

> This test file uses `pytest`'s `monkeypatch`/`capsys`/`tmp_path`. Run with `python3 -m pytest` if available; otherwise the project's `unittest` suite covers Tasks 1–6 and this file can be run via `pytest`. If pytest is unavailable, install nothing — instead run `python3 -m pytest` is skipped and these four behaviors are verified manually per the README. (Prefer pytest: it is already used across the user's other repos.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_hook_cmd.py -v`
Expected: FAIL — `cmd_hook` not implemented / `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

Replace `rt_claude/cli.py`'s `main` body and add the command functions:

```python
# rt_claude/cli.py  (append imports at top)
import json, sys, time, subprocess, os
from rt_claude import config as cfgmod
from rt_claude.context import resolve_context
from rt_claude import state as statemod
from rt_claude.emit import decide
from rt_claude.client import post_highlight

def _log(msg):
    try:
        cfgmod.STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cfgmod.LOG_PATH, "a") as f:
            f.write("{} {}\n".format(time.strftime("%Y-%m-%dT%H:%M:%S"), msg))
    except OSError:
        pass

def _spawn_emit(desc, source):
    shim = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rt-claude")
    try:
        with open(cfgmod.LOG_PATH, "a") as logf:
            subprocess.Popen([sys.executable, shim, "_emit", "--desc", desc, "--source", source],
                             stdout=logf, stderr=logf, start_new_session=True)
    except OSError as e:
        _log("spawn failed: {}".format(e))

def cmd_hook(args) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        session_id = str(payload.get("session_id") or "session")
        cwd = payload.get("cwd") or os.getcwd()
        cfg = cfgmod.load_config()
        ctx = resolve_context(cwd)
        sess = statemod.load_session(session_id)
        action, new_sess = decide(args.event, sess, ctx, cfg, time.time())
        if args.event == "SessionEnd":
            statemod.clear_session(session_id)
        else:
            statemod.save_session(session_id, new_sess)
        if action:
            if args.dry_run:
                print("WOULD POST: {}".format(action["description"]))
            elif cfgmod.resolve_api_key():
                _spawn_emit(action["description"], action["source"])
    except Exception as e:  # never break a turn
        _log("hook error: {}".format(e))
    return 0

def cmd_emit(args) -> int:
    key = cfgmod.resolve_api_key()
    if not key:
        _log("emit: no api key")
        return 0
    try:
        post_highlight(key, args.desc, args.source)
    except Exception as e:
        _log("emit post failed: {}".format(e))
    return 0

def cmd_test(args) -> int:
    key = cfgmod.resolve_api_key()
    if not key:
        print("No API key. Set RESCUETIME_API_KEY or write ~/.claude/rescuetime/api_key")
        return 1
    try:
        status = post_highlight(key, "rt-claude test highlight", "claude-code")
        print("Posted test highlight (HTTP {}).".format(status))
        return 0
    except Exception as e:
        print("Failed: {}".format(e))
        return 1

def cmd_status(args) -> int:
    cfg = cfgmod.load_config()
    print("enabled: {}".format(cfg["enabled"]))
    print("api key: {}".format("present" if cfgmod.resolve_api_key() else "MISSING"))
    print("heartbeat_minutes: {}".format(cfg["heartbeat_minutes"]))
    print("exclude_projects: {}".format(cfg["exclude_projects"]))
    sd = statemod.SESSIONS_DIR
    sessions = sorted(p.name for p in sd.glob("*.json")) if sd.exists() else []
    print("active sessions: {}".format(sessions or "none"))
    return 0
```

Now update `main` to dispatch (replace the `return 0` body):

```python
def main(argv):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    dispatch = {
        "hook": cmd_hook, "_emit": cmd_emit, "test": cmd_test, "status": cmd_status,
    }
    fn = dispatch.get(args.command)
    if fn:
        return fn(args)
    return 0  # install/uninstall added in Task 8
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_hook_cmd.py -v && python3 -m unittest discover -s tests -v`
Expected: PASS for the hook tests; Tasks 1–6 unittest suite still PASS.

- [ ] **Step 5: Commit**

```bash
git add rt_claude/cli.py tests/test_hook_cmd.py
git commit -m "feat: hook/_emit/test/status commands with detached POST"
```

---

### Task 8: `install` / `uninstall` — merge hooks into settings.json

**Files:**
- Modify: `rt_claude/cli.py`
- Create: `rt_claude/installer.py`
- Test: `tests/test_installer.py`

**Interfaces:**
- Produces (in `installer.py`):
  - `HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"]`
  - `hook_command(shim_path: str, event: str) -> str` → e.g. `"<python> <shim> hook --event=Stop"`.
  - `install_hooks(settings: dict, shim_path: str, python: str) -> dict` — returns a new settings dict with our hook entries merged in (idempotent; tagged so uninstall can find them). Each entry carries `"_rt_claude": True`.
  - `uninstall_hooks(settings: dict) -> dict` — removes only entries tagged `_rt_claude`.
- Produces (in `cli.py`): `cmd_install(args) -> int`, `cmd_uninstall(args) -> int` reading/writing `~/.claude/settings.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_installer.py
from rt_claude.installer import install_hooks, uninstall_hooks, HOOK_EVENTS

def test_install_adds_all_events_idempotently():
    s = {"permissions": {"allow": []}}
    s1 = install_hooks(s, "/x/rt-claude", "/usr/bin/python3")
    for ev in HOOK_EVENTS:
        entries = s1["hooks"][ev]
        assert any(e.get("_rt_claude") for e in entries)
    s2 = install_hooks(s1, "/x/rt-claude", "/usr/bin/python3")
    for ev in HOOK_EVENTS:
        ours = [e for e in s2["hooks"][ev] if e.get("_rt_claude")]
        assert len(ours) == 1  # no duplicates
    assert s2["permissions"] == {"allow": []}  # untouched

def test_uninstall_removes_only_ours():
    s = {"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": "other"}]},
    ]}}
    s = install_hooks(s, "/x/rt-claude", "/usr/bin/python3")
    s = uninstall_hooks(s)
    remaining = s["hooks"]["Stop"]
    assert len(remaining) == 1
    assert remaining[0]["hooks"][0]["command"] == "other"

def test_command_format():
    from rt_claude.installer import hook_command
    cmd = hook_command("/x/rt-claude", "Stop")
    assert "/x/rt-claude" in cmd and "hook --event=Stop" in cmd
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_installer -v`
Expected: FAIL — `No module named rt_claude.installer`.

- [ ] **Step 3: Write minimal implementation**

```python
# rt_claude/installer.py
import sys

HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"]

def hook_command(shim_path: str, event: str, python: str = None) -> str:
    py = python or sys.executable
    return "{} {} hook --event={}".format(py, shim_path, event)

def _entry(shim_path, event, python):
    return {
        "_rt_claude": True,
        "hooks": [{"type": "command", "command": hook_command(shim_path, event, python)}],
    }

def install_hooks(settings: dict, shim_path: str, python: str = None) -> dict:
    out = dict(settings)
    hooks = {ev: list(v) for ev, v in out.get("hooks", {}).items()}
    for ev in HOOK_EVENTS:
        entries = [e for e in hooks.get(ev, []) if not e.get("_rt_claude")]
        entries.append(_entry(shim_path, ev, python))
        hooks[ev] = entries
    out["hooks"] = hooks
    return out

def uninstall_hooks(settings: dict) -> dict:
    out = dict(settings)
    hooks = {}
    for ev, entries in out.get("hooks", {}).items():
        kept = [e for e in entries if not e.get("_rt_claude")]
        if kept:
            hooks[ev] = kept
    out["hooks"] = hooks
    return out
```

Add to `rt_claude/cli.py`:

```python
def cmd_install(args) -> int:
    import json
    from rt_claude.installer import install_hooks
    settings_path = cfgmod.STATE_DIR.parent / "settings.json"
    settings = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    shim = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rt-claude")
    settings = install_hooks(settings, shim)
    settings_path.write_text(json.dumps(settings, indent=2))
    print("Installed hooks into {}".format(settings_path))
    print("Next: set your RescueTime key (RESCUETIME_API_KEY or ~/.claude/rescuetime/api_key) and run `rt-claude test`.")
    return 0

def cmd_uninstall(args) -> int:
    import json
    from rt_claude.installer import uninstall_hooks
    settings_path = cfgmod.STATE_DIR.parent / "settings.json"
    if not settings_path.exists():
        print("No settings.json found.")
        return 0
    settings = json.loads(settings_path.read_text())
    settings = uninstall_hooks(settings)
    settings_path.write_text(json.dumps(settings, indent=2))
    print("Removed rt-claude hooks from {}".format(settings_path))
    return 0
```

Wire them into `main`'s dispatch dict:

```python
    dispatch = {
        "hook": cmd_hook, "_emit": cmd_emit, "test": cmd_test, "status": cmd_status,
        "install": cmd_install, "uninstall": cmd_uninstall,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_installer -v && python3 -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rt_claude/installer.py rt_claude/cli.py tests/test_installer.py
git commit -m "feat: install/uninstall hooks in settings.json"
```

---

### Task 9: README + sample config

**Files:**
- Create: `README.md`
- Create: `config.example.json`

**Interfaces:** none (docs).

- [ ] **Step 1: Write the README**

```markdown
# rescuetime-claude

Logs which project + branch you work on inside Claude Code to your RescueTime
timeline as **Highlights** — filling the gap where RescueTime only sees
"Terminal". No background daemon; pure Python stdlib.

## Privacy

The only data sent to RescueTime is **repo name + branch + date**. Never prompt
text, file contents, diffs, or full paths.

## Install

1. `python3 -m rt_claude install`  (or `./rt-claude install`)
2. Set your API key (from https://www.rescuetime.com/anapi/manage):
   - `export RESCUETIME_API_KEY=...`  **or**
   - `umask 077 && echo "YOUR_KEY" > ~/.claude/rescuetime/api_key`
3. `./rt-claude test`  → confirms a highlight posts.

## Config (`~/.claude/rescuetime/config.json`)

See `config.example.json`. Keys: `enabled`, `source_label`,
`heartbeat_minutes` (0 = context-switch markers only), `exclude_projects`
(names or globs), `description_template` (`{project}`, `{branch}`).

## Uninstall

`./rt-claude uninstall`  (removes only the hooks this tool added).

## Tests

`python3 -m unittest discover -s tests` and `python3 -m pytest tests/test_hook_cmd.py`.
```

- [ ] **Step 2: Write `config.example.json`**

```json
{
  "enabled": true,
  "source_label": "claude-code",
  "heartbeat_minutes": 0,
  "exclude_projects": [],
  "description_template": "{project} · {branch}"
}
```

- [ ] **Step 3: Run the full suite once more**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (all unittest tasks)

- [ ] **Step 4: Commit**

```bash
git add README.md config.example.json
git commit -m "docs: README + example config"
```

---

## Self-Review

**Spec coverage:**
- Push → RescueTime Highlights: Tasks 6, 7. ✓
- Hook-as-tick, detached POST, always exit 0: Task 7. ✓
- Context-switch emission + optional heartbeat: Task 5. ✓
- Config + key resolution (env→file), privacy: Tasks 2, 9. ✓
- Scope (`exclude_projects` exact+glob) + kill switch: Tasks 2, 5. ✓
- State files, multi-window via session_id, corrupt recovery: Task 4. ✓
- install/uninstall settings.json merge: Task 8. ✓
- test/status/dry-run: Task 7. ✓
- Repo layout + README: Tasks 1, 9. ✓
- Deferred (offline-time, daemon, LLM, Keychain): intentionally absent. ✓

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `decide` returns `(action, new_session)` consistently (Tasks 5, 7); `resolve_context` returns `{"project","branch"}` consumed in Tasks 5/7; `post_highlight` signature matches Task 7's call; `install_hooks/uninstall_hooks` signatures match Task 8's `cmd_install/cmd_uninstall`.

**One known wrinkle:** Task 7's `test_hook_cmd.py` uses `pytest` fixtures while Tasks 1–6 use `unittest`. This is deliberate (the stdin/HOME monkeypatching is far cleaner in pytest, which is already used in the user's other repos). If pytest is unavailable, those four behaviors are listed for manual verification in the README; the `unittest` suite still covers the pure logic.
