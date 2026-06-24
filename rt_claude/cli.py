import argparse
import json
import sys
import time
import subprocess
import os

from rt_claude import config as cfgmod
from rt_claude.context import resolve_context
from rt_claude import state as statemod
from rt_claude.emit import decide
from rt_claude.client import post_highlight


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


def cmd_install(args) -> int:
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


def main(argv):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    dispatch = {
        "hook": cmd_hook,
        "_emit": cmd_emit,
        "test": cmd_test,
        "status": cmd_status,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
    }
    fn = dispatch.get(args.command)
    if fn:
        return fn(args)
    return 0
