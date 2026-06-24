# rt-claude

`rt-claude` sends Claude Code session highlights to [RescueTime](https://www.rescuetime.com/), letting you track time spent across repos and branches automatically — without any manual logging.

## What it does

Each time a Claude Code hook fires (session start, prompt submit, stop, session end), `rt-claude` reads the git repo name and current branch from the working directory, then posts a highlight to the RescueTime Highlights API. The foreground hook exits immediately (no network latency); the actual HTTP POST is dispatched to a detached background process.

## Install

```sh
# 1. Clone or copy this repo somewhere permanent, e.g.:
git clone https://github.com/bcamarneiro/rescuetime-claude ~/.local/share/rt-claude

# 2. Make the shim executable
chmod +x ~/.local/share/rt-claude/rt-claude

# 3. Set your RescueTime API key (get it at rescuetime.com/anapi/manage)
export RESCUETIME_API_KEY=your_key_here
# Or write it to a file (never committed):
echo "your_key_here" > ~/.claude/rescuetime/api_key

# 4. Wire Claude Code hooks
~/.local/share/rt-claude/rt-claude install

# 5. Verify
~/.local/share/rt-claude/rt-claude test
```

## Usage

### Hook events

Claude Code calls the hook automatically. The following events are wired by `install`:

| Event | Behavior |
|---|---|
| `SessionStart` | Posts on new repo/branch context |
| `UserPromptSubmit` | Posts on context change or heartbeat |
| `Stop` | Posts on context change |
| `SessionEnd` | Clears session state, no post |

### Dry run

Preview what would be posted without sending anything:

```sh
rt-claude --dry-run hook --event SessionStart <<< '{"session_id":"s1","cwd":"/path/to/repo"}'
```

### Status

Show current configuration and active session files:

```sh
rt-claude status
```

### Test

Post a one-off test highlight to verify your API key works:

```sh
rt-claude test
```

### Uninstall

Remove the hooks from `~/.claude/settings.json`:

```sh
rt-claude uninstall
```

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
| `source_label` | `"claude-code"` | Source tag shown in RescueTime highlights |
| `heartbeat_minutes` | `0` | Re-post every N minutes on the same context (0 = only on context change) |
| `exclude_projects` | `[]` | List of repo names or glob patterns to skip (e.g. `["dotfiles", "tmp-*"]`) |
| `description_template` | `"{project} · {branch}"` | Template for the highlight description; `{project}` = repo name, `{branch}` = branch name |

## Privacy

Only the **repo name**, **branch name**, and **date** are ever sent to RescueTime. No code, no file paths, no prompt content, no personal data. The API key is read from an environment variable or a local file — it is never written to config or committed to the repo.
