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
