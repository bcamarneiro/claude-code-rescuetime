# rescuetime-claude — design

**Date:** 2026-06-24
**Status:** approved (minimal scope)
**Author:** Bruno Camarneiro (with Claude)

## Goal

Push what you work on inside Claude Code into RescueTime, so your RescueTime
timeline is annotated with **which project and branch** you were on. RescueTime
auto-tracks that you were in the terminal/editor, but it's blind to *what* that
terminal time was about — this fills exactly that blind spot.

## Non-goals (explicitly deferred)

- **No pulling RescueTime data back into Claude** (read direction). Push only.
- **No per-project duration totals** in this version (that needs Offline-Time
  blocks — see Future).
- **No background daemon / launchd agent.** Hooks do the work.
- **No LLM-generated summaries.** Labels come from cheap local context
  (repo name + branch).

## Decisions log

The idea was scoped through brainstorming. Key forks and what we chose:

| Fork | Choice | Why |
|---|---|---|
| Data flow | **Push Claude Code → RescueTime** | Fills the blind spot RescueTime can't see on its own. |
| Record primitive | **Highlights** (annotations) | Ride on top of already-tracked terminal time; no double-counting, no 4h cap. Offline-Time deferred. |
| Cadence | **Context-switch markers** (heartbeat optional, default off) | Identical dated highlights just clutter; the "what I worked on and when I switched" trail is the useful signal. |
| Architecture | **Hook-as-tick, no daemon** | Crash-resilient enough, near-zero moving parts, fits the existing all-hooks setup. Started minimal deliberately; the heavier hybrid (daemon + offline-time) is a known upgrade path, not thrown-away work. |

> Note on the pivot: earlier in brainstorming the heavier options (heartbeat,
> hybrid daemon, both primitives) were each picked, then we consciously pulled
> back to the minimal end on a YAGNI basis. Ship this, live with it a week, and
> only add the daemon/durations if the gap is actually felt.

## Architecture

Hooks make the *decision* locally (an instant state-file read) and, when they
decide to post, **spawn a detached background process** to do the HTTPS call,
then return `0` immediately. Claude Code never waits on the network.

```
Claude Code hook fires
   │  (hook JSON on stdin: session_id, cwd)
   ▼
rt-claude hook --event=<name>                 ~/.claude/rescuetime/
   1. resolve context: git repo + branch          sessions/<session_id>.json
      (fallback: cwd basename)                      { project, branch,
   2. compare to this session's last-emitted          last_emit_at, last_context }
      context
   3. decide: emit? (emission rules below)
   4. if emit → spawn DETACHED background POST,
               update session state
   5. exit 0  (always, instantly)
        │
        └─ background: POST https://www.rescuetime.com/anapi/highlights_post
                       { key, highlight_date=YYYY-MM-DD,
                         description="<project> · <branch>", source="claude-code" }
```

### Why this is safe to put on the hook path

- The hook is a local file read + a `fork`/detached spawn. No network in the
  foreground.
- It is wrapped to **always exit 0** (see Error handling).

## Components

A single stdlib-only Python 3 CLI, `rt-claude` (no pip dependencies; runs on
macOS as shipped). Subcommands:

- `rt-claude hook --event=<SessionStart|UserPromptSubmit|Stop|SessionEnd>`
  — invoked by the hooks. Reads hook JSON on stdin (`session_id`, `cwd`, …),
  resolves context, applies emission rules, updates session state, optionally
  spawns the detached POST.
- `rt-claude install` — merges the hook entries into `~/.claude/settings.json`
  (additive; never clobbers existing config) and prints next steps.
- `rt-claude uninstall` — removes only the entries it added.
- `rt-claude test` — posts a single highlight dated today to verify the API key.
- `rt-claude status` — prints config, key presence, and live session state.
- `--dry-run` (global flag) — print the would-be POST instead of sending.

## Emission rules

Context key = `project + branch`.

- **SessionStart** → emit once: `hoursmith · staging` (you started here).
- **UserPromptSubmit / Stop** → tick: if `project` or `branch` changed since the
  last emit for this session → emit immediately. Otherwise do nothing.
- **Optional heartbeat** (`heartbeat_minutes`, default `0` = off): if set > 0,
  also re-emit a "still on X" highlight after N minutes of continued activity
  within the same context. Off by default.
- **SessionEnd** → finalize/remove the session state file. No post (highlights
  carry no duration, so a "stopped" marker adds nothing).

Resulting timeline: a clean trail of dated, labeled markers, e.g.
`hoursmith · staging` → `hoursmith · fix/csp…` → `bruno-docs · main`.

## Configuration

`~/.claude/rescuetime/config.json`:

```json
{
  "enabled": true,
  "source_label": "claude-code",
  "heartbeat_minutes": 0,
  "exclude_projects": ["secret-client-repo"],
  "description_template": "{project} · {branch}"
}
```

- `enabled` — global kill switch.
- `source_label` — RescueTime `source` param, groups these in the UI.
- `heartbeat_minutes` — 0 disables periodic re-emit.
- `exclude_projects` — repo names / path globs to skip entirely.
- `description_template` — `{project}`, `{branch}` placeholders.

### API key storage (out of config, out of git)

Resolution order:

1. `RESCUETIME_API_KEY` environment variable.
2. `~/.claude/rescuetime/api_key` file, created `chmod 600`.

(macOS Keychain is an optional later upgrade.) If no key is found, the hook is a
**silent no-op** — never an error.

## Scope & privacy

- Runs for **all projects by default**; `exclude_projects` opts sensitive repos
  out; `enabled:false` is the master switch.
- The **only** data that leaves the machine is **repo name + branch + date**.
  No prompt text, no file contents, no diffs, no full paths (basename only).
- API key lives in env or a `chmod 600` file, never committed. `.gitignore`
  covers `api_key` and the runtime state dir.

## Error handling

The hook path is wrapped so it **always exits 0**. Missing key, unreadable or
corrupt state, malformed hook JSON, or a network failure all degrade to "do
nothing, append one line to `~/.claude/rescuetime/rt-claude.log`."

- A dropped highlight is low-stakes; **never blocking or failing a turn** is the
  priority.
- The background POST has a ~5s timeout and is **not retried** (keeps it
  daemon-free). Failures are logged, not surfaced.
- Corrupt session state file → treated as empty and rewritten.

## Testing

Logic is structured as pure functions so it tests without network or hooks.

- **Unit (`unittest`, stdlib):**
  - emission decision (context-switch vs throttle vs heartbeat),
  - description formatting + 255-char truncation,
  - `exclude_projects` matching (name + glob),
  - RescueTime client with mocked `urllib` — asserts endpoint, params, and
    `YYYY-MM-DD` date format,
  - session-state round-trip + corrupt-state recovery,
  - key resolution order (env over file; absent → no-op).
- **Integration:** `--dry-run` prints the would-be POST; `rt-claude test` does
  one real POST.
- **Manual:** install, run sessions across two repos, confirm the labeled
  markers and the switch between them appear on the RescueTime timeline.

## Repository layout

Standalone repo at `~/Projects/bcamarneiro/rescuetime-claude`.

```
rescuetime-claude/
  rt_claude/                 # package: cli.py, context.py, emit.py, client.py, state.py, config.py
  tests/
  docs/superpowers/specs/2026-06-24-rescuetime-claude-design.md
  README.md                  # what it is, install, the privacy surface (repo+branch only)
  .gitignore                 # api_key, state dir, __pycache__
```

## Future / upgrade path (not now)

These are the deferred heavier options, kept compatible with this design:

1. **Offline-Time mode** — add a `mode: "offline_time"` that maintains rolling
   per-project time blocks (real durations, 4h-cap splitting). Needed only if
   you want per-project totals and accept overlap with auto-tracked terminal
   time.
2. **Hybrid daemon (true wall-clock)** — promote the session registry the hooks
   already maintain into a launchd agent that flushes every N min, for accurate
   long-turn / idle-present capture and multi-window aggregation. The hook
   registry from this design is exactly its input, so this is additive.
3. **LLM one-line summaries** — richer descriptions than `project · branch`.
4. **macOS Keychain** for the API key.
