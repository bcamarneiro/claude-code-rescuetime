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

ISSUE_URL = "https://github.com/bcamarneiro/claude-code-rescuetime/issues/1"
KEY_PAGE_URL = "https://www.rescuetime.com/anapi/manage"


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
    sk = sub.add_parser("set-key", help="Save your RescueTime API key")
    sk.add_argument("key", nargs="?", default=None)
    sub.add_parser("setup", help="Open the RescueTime key page and explain how to save your key")
    return p


def _log(msg):
    try:
        cfgmod.STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cfgmod.LOG_PATH, "a") as f:
            f.write("{} {}\n".format(time.strftime("%Y-%m-%dT%H:%M:%S"), msg))
    except OSError:
        pass


def _detach_kwargs(platform=None):
    """Popen kwargs that detach the background POST from the hook process.

    POSIX uses a new session (setsid); Windows has no setsid, so it uses
    DETACHED_PROCESS + a new process group instead.
    """
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
        )
        return {"creationflags": flags}
    return {"start_new_session": True}


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
    cfgmod.write_api_key(key, cfgmod.API_KEY_PATH)
    print("Saved key to {}".format(cfgmod.API_KEY_PATH))
    try:
        status = post_highlight(key, "rt-claude setup test", "claude-code")
        print("Verified — test highlight posted (HTTP {}).".format(status))
    except Exception as e:
        print("Saved, but the test post failed ({}). Double-check the key.".format(e))
    return 0


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


def _spawn_emit(desc, source):
    cfgmod.STATE_DIR.mkdir(parents=True, exist_ok=True)
    shim = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rt-claude")
    try:
        with open(cfgmod.LOG_PATH, "a") as logf:
            subprocess.Popen([sys.executable, shim, "_emit", "--desc", desc, "--source", source],
                             stdout=logf, stderr=logf, **_detach_kwargs())
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
        notice = _first_run_notice()
        if notice:
            # systemMessage is surfaced to the user by Claude Code without
            # polluting the model context.
            print(json.dumps({"systemMessage": notice}))
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
    if sys.platform == "win32":
        print("platform: Windows — best-effort & unverified; please report at {}".format(ISSUE_URL))
    return 0


def cmd_install(args) -> int:
    from rt_claude.installer import install_hooks
    settings_path = cfgmod.STATE_DIR.parent / "settings.json"
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, ValueError):
            print("Could not parse {} (invalid JSON); aborting.".format(settings_path))
            return 1
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
    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, ValueError):
        print("Could not parse {} (invalid JSON); aborting.".format(settings_path))
        return 1
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
        "set-key": cmd_set_key,
        "setup": cmd_setup,
    }
    fn = dispatch.get(args.command)
    if fn:
        return fn(args)
    return 0
