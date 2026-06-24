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
