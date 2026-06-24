# claude-code-rescuetime

Log which **project and branch** you work on inside [Claude Code](https://claude.com/claude-code) to your [RescueTime](https://www.rescuetime.com/) timeline as **Highlights**.

RescueTime already tracks that you were in your terminal/editor — but while you're in Claude Code it only sees "Terminal", blind to *what* you were working on. This fills that gap: a clean, dated trail of `myrepo · main` → `myrepo · fix/login` → `other-repo · main`, annotating the time RescueTime is already tracking. It's [`git-commits-to-rescuetime-daily-highlights`](https://github.com/RescueTime/git-commits-to-rescuetime-daily-highlights) reimagined for AI coding sessions instead of commits.

- **No daemon.** Pure Claude Code hooks.
- **No dependencies.** Standard-library Python 3.9+ only.
- **Private by design.** The only data sent to RescueTime is **repo name + branch + date** — never prompts, code, file contents, or paths.

## Install (as a Claude Code plugin — recommended)

```text
/plugin marketplace add bcamarneiro/claude-code-rescuetime
/plugin install claude-code-rescuetime@claude-code-rescuetime
```

Then set your RescueTime API key (from <https://www.rescuetime.com/anapi/manage>):

```sh
mkdir -p ~/.claude/rescuetime
umask 077 && echo "YOUR_KEY" > ~/.claude/rescuetime/api_key   # or: export RESCUETIME_API_KEY=YOUR_KEY
```

That's it — the plugin wires the hooks automatically. Until a key is present, the hooks are a silent no-op.

### First-time setup

After installing, run:

```text
/rescuetime-setup
```

It opens the RescueTime API-key page and saves your key — privately if you use the printed terminal command, or conveniently if you paste the key into the chat. On a fresh install you'll also be nudged to run it. To check or re-test later: `/rescuetime-status` and `/rescuetime-test`.

## Install (manual / without the plugin system)

```sh
git clone https://github.com/bcamarneiro/claude-code-rescuetime ~/.local/share/claude-code-rescuetime
cd ~/.local/share/claude-code-rescuetime
chmod +x rt-claude
echo "YOUR_KEY" > ~/.claude/rescuetime/api_key   # umask 077 first
./rt-claude install     # writes the hooks into ~/.claude/settings.json
./rt-claude test        # confirm a highlight posts
```

> **Use one method, not both.** The plugin and `./rt-claude install` each register the same hooks — running both double-posts. If you installed the plugin, don't also run `install` (and vice-versa).

## How it works

Each time a Claude Code hook fires (`SessionStart`, `UserPromptSubmit`, `Stop`, `SessionEnd`), the tool reads the git repo + branch from the session's working directory and, **only when the context changed** since the last post, dispatches a highlight to the RescueTime Highlights API. The foreground hook returns instantly — the actual HTTP POST runs in a detached background process, so it never adds latency to a turn, and a network failure can never break your session.

| Event | Behavior |
|---|---|
| `SessionStart` | Post once for the starting repo/branch |
| `UserPromptSubmit` | Post when repo/branch changed (or on heartbeat, if enabled) |
| `Stop` | Post when repo/branch changed |
| `SessionEnd` | Clear session state, no post |

## Configuration

Create `~/.claude/rescuetime/config.json` to override defaults:

```json
{
  "enabled": true,
  "source_label": "claude-code",
  "heartbeat_minutes": 0,
  "exclude_projects": [],
  "description_template": "{project} · {branch}"
}
```

| Field | Default | Description |
|---|---|---|
| `enabled` | `true` | Set to `false` to pause all posting |
| `source_label` | `"claude-code"` | Source tag shown in RescueTime |
| `heartbeat_minutes` | `0` | Re-post every N minutes on the same context (0 = only on context change) |
| `exclude_projects` | `[]` | Repo names or glob patterns to skip (e.g. `["dotfiles", "client-*"]`) |
| `description_template` | `"{project} · {branch}"` | `{project}` = repo name, `{branch}` = branch name |

## Commands

If you installed the **plugin**, two slash commands are available in Claude Code:

| Command | Does |
|---|---|
| `/rescuetime-status` | Show config + active sessions and whether your API key is detected |
| `/rescuetime-test` | Post a one-off test highlight to verify your key |

For the **manual / CLI** install, the same plus a couple more are on the shim:

```sh
./rt-claude status      # config + active sessions
./rt-claude test        # post a one-off test highlight
./rt-claude --dry-run hook --event SessionStart <<< '{"session_id":"s1","cwd":"/path/to/repo"}'  # preview, posts nothing
./rt-claude uninstall   # remove the hooks this tool added from settings.json
```

## Privacy

Only the **repo name**, **branch name**, and **date** are ever sent to RescueTime. No code, no file paths, no prompt content. The API key is read from `RESCUETIME_API_KEY` or `~/.claude/rescuetime/api_key` (keep it `chmod 600`); it is never written to config or committed.

## Requirements

- Python 3.9+ (uses only the standard library), on `PATH` as either `python3` or `python`
- A RescueTime account with API access

### Platform support

- **macOS / Linux** — fully supported (maintainer-tested).
- **Windows** — best-effort. The hooks try `python3` then fall back to `python`, and the background POST uses Windows `DETACHED_PROCESS` creation flags instead of the POSIX session detach. Requires Python on `PATH` as `python` (the default for the python.org installer).

> **🪟 Help wanted — Windows testers.** Windows support is implemented but **not yet verified on a real Windows machine**. If you run it on Windows, please report whether it works (or doesn't) in **[issue #1](https://github.com/bcamarneiro/claude-code-rescuetime/issues/1)** — there's a 5-minute test checklist there. On first run, the plugin will also point you to that issue. A single confirmation turns Windows from "best-effort" into "supported." 🙏

## License

[MIT](./LICENSE)
