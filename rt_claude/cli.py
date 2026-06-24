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
