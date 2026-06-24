# claude-code-rescuetime — guided setup wizard design

**Date:** 2026-06-24
**Status:** approved
**Author:** Bruno Camarneiro (with Claude)

## Goal

Remove the friction of connecting RescueTime. Today a user must find the API-key
page, copy the key, and place it in `~/.claude/rescuetime/api_key` by hand. This
adds an **after-install onboarding nudge** plus a **`/rescuetime-setup` wizard**
that opens the key page in the browser and saves the key for them — staying
backendless, stdlib-only, and private.

## Why not OAuth or the desktop daemon (research outcome)

Both were investigated and rejected:

- **Local daemon** — RescueTime's desktop app keeps an encrypted local cache and
  syncs to RescueTime's servers; it exposes **no local API/socket/token** for
  third-party tools. Reading its stored credentials would be undocumented and a
  security anti-pattern. Not viable.
- **Browser OAuth** — RescueTime OAuth2 requires (a) a **manually provisioned**
  app ("contact us"), (b) **only `authorization_code` grant — no PKCE/device
  flow**, so a **`client_secret` is required**. A distributed open-source CLI
  can't ship a secret safely; doing OAuth properly would need a **hosted
  token-broker backend**, which breaks this tool's no-backend/privacy-first
  ethos. RescueTime's own docs recommend **API keys** for "a personal dashboard,
  a script, an automation" — exactly what this plugin is.

So: keep the API key, make obtaining + storing it nearly frictionless.

## Components

### 1. After-install onboarding nudge (first-run, key-missing)

There is **no install-time hook** for plugins, so "after install" is approximated
by **first-run detection** — the standard pattern. The existing one-time notice
mechanism (currently `_windows_first_run_notice`) is **replaced by a unified
`_first_run_notice()`** that composes a single message, emitted **once** via a
single marker `~/.claude/rescuetime/first-run-notice-shown`, as one
`systemMessage` (user-facing; not injected into model context → no token cost):

- If **no API key** is configured → include:
  *"👋 claude-code-rescuetime is installed but not connected. Run `/rescuetime-setup` to link your RescueTime account."*
- If **`sys.platform == "win32"`** → also include the existing Windows
  best-effort/unverified caveat + issue link.

If neither line applies (key already set, non-Windows), nothing is emitted and
the marker is **not** written (so the nudge can still fire on a later session if
the user is still unconfigured). The marker is written only when a message is
actually shown.

### 2. CLI: `rt-claude setup`

Opens the browser to the key page and prints next-step instructions.

- Uses stdlib `webbrowser.open("https://www.rescuetime.com/anapi/manage")`
  (cross-platform: macOS/Linux/Windows, no new deps).
- Prints two ways to finish, **leading with the private one**:
  1. *(recommended, fully local)* "In your own terminal, run:
     `<python> <abs shim path> set-key` and paste your key at the hidden prompt."
     — computed absolute path so it's copy-pasteable.
  2. *(convenient)* "Or paste the key here and I'll save it."
- Returns 0 even if the browser can't open (prints the URL to visit manually).

### 3. CLI: `rt-claude set-key [KEY]`

Writes the key to `~/.claude/rescuetime/api_key` with restrictive permissions.

- Key source precedence: positional `KEY` arg → else if stdin is a TTY, prompt
  with `getpass.getpass("RescueTime API key: ")` (hidden, never echoed) → else
  read one line from stdin.
- Reject empty/whitespace key → print error, return 1.
- Write atomically with mode `0o600`: `os.open(path, O_WRONLY|O_CREAT|O_TRUNC,
  0o600)` then write; follow with a best-effort `os.chmod(path, 0o600)` wrapped
  in `try/except OSError` (POSIX enforces; Windows honors what it can — best
  effort, documented).
- After saving, attempt a verification post via the existing `post_highlight`
  and print the result (success/HTTP code, or a clear "saved, but the test post
  failed — check the key" message). Saving must succeed even if the test fails.

### 4. Slash command: `/rescuetime-setup`

`commands/rescuetime-setup.md` runs `rt-claude setup` (opens the browser via the
`python3 … || python …` fallback, gated by `allowed-tools: Bash(python3:*),
Bash(python:*)`), then instructs Claude to:

- **Recommend the private path**: tell the user to run the printed
  `set-key` command in their own terminal (key never enters the chat/model).
- **Offer the convenient path**: if the user pastes the key into chat, Claude
  saves it by running `rt-claude set-key "<pasted key>"`, then confirms via the
  test post.

## Data flow

```
First session after install, no key
  → hook → _first_run_notice() → systemMessage "run /rescuetime-setup" (once)

User runs /rescuetime-setup
  → rt-claude setup → webbrowser.open(key page) + prints both finish paths
  → (private)    user runs `rt-claude set-key` in their terminal → getpass → api_key (0600) → test
  → (convenient) user pastes key in chat → Claude runs `rt-claude set-key "<key>"` → api_key (0600) → test
```

## Privacy

- **Default (terminal `set-key` with getpass):** the key never enters the chat,
  the model context, or shell history. Fully local.
- **Convenient (chat paste):** the key passes through the model context once.
  Acceptable for a low-sensitivity RescueTime highlights key; explicitly the
  non-default, and called out in the wizard text.
- The key file is `0o600` on POSIX (best-effort on Windows). Never committed
  (already git-ignored).

## Error handling

- `setup`: browser fails to open → print the URL to visit manually; return 0.
- `set-key`: empty key → error + return 1; file-write failure → error + return 1;
  test-post failure → key still saved, warn and return 0.
- The hook notice path remains wrapped so the hook **always exits 0**; a failure
  building/emitting the notice degrades to no-op + log line.

## Testing (stdlib `unittest`)

- `set-key`: writes the file with the key; rejects empty/whitespace (return 1);
  resulting file mode is `0o600` on POSIX (skip the mode assertion on Windows);
  reads from arg vs stdin.
- `setup`: calls `webbrowser.open` with the correct URL (inject/mock the opener);
  returns 0 even when the opener raises.
- `_first_run_notice()`: emits the setup line when no key + not-yet-shown; emits
  the Windows line on `win32`; emits both when both apply; emits nothing (and
  writes no marker) when key present + non-Windows; never fires twice (marker).
- Existing `_windows_first_run_notice` test is migrated to the unified function.

## Scope

2 new CLI subcommands (`setup`, `set-key`), 1 new slash command
(`/rescuetime-setup`), and a refactor of the first-run notice into a unified,
key-aware function. No OAuth, no backend, no new dependencies. Version bump to
**0.3.0** (new user-facing feature).

## Out of scope / future

- OAuth (would require a hosted token-broker — revisit only if RescueTime adds
  PKCE/device flow).
- Auto-detecting an existing key from other tools.
