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
