---
description: Connect your RescueTime account — opens the API-key page and saves your key
allowed-tools: Bash(python3:*), Bash(python:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/rt-claude" setup || python "${CLAUDE_PLUGIN_ROOT}/rt-claude" setup`

The command above opened the RescueTime API-key page in the browser and printed two ways to finish. Guide the user:

- **Recommend the private path:** have them run the printed `set-key` command in their *own* terminal and paste the key at the hidden prompt — this keeps the key out of this chat entirely.
- **If they paste the key here instead:** save it for them by running `python3 "${CLAUDE_PLUGIN_ROOT}/rt-claude" set-key "<the key they pasted>"` (fall back to `python` if `python3` is missing), then report whether the verification highlight posted. Note that pasting here means the key passed through this conversation.
