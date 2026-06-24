---
description: Show claude-code-rescuetime status — config, active sessions, and whether your RescueTime API key is detected
allowed-tools: Bash(python3:*), Bash(python:*)
---

Current claude-code-rescuetime status:

!`python3 "${CLAUDE_PLUGIN_ROOT}/rt-claude" status || python "${CLAUDE_PLUGIN_ROOT}/rt-claude" status`

Summarize the output above. If the API key shows as MISSING, explain how to set it: either `export RESCUETIME_API_KEY=<key>` or write the key into `~/.claude/rescuetime/api_key` (create it with `umask 077` so it's chmod 600). The key comes from https://www.rescuetime.com/anapi/manage.
