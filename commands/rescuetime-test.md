---
description: Post a test highlight to RescueTime to verify your claude-code-rescuetime API key works
allowed-tools: Bash(python3:*), Bash(python:*)
---

Posting a one-off test highlight to verify the RescueTime integration:

!`python3 "${CLAUDE_PLUGIN_ROOT}/rt-claude" test || python "${CLAUDE_PLUGIN_ROOT}/rt-claude" test`

Interpret the result for me: "Posted test highlight (HTTP 200)" means it works — check your RescueTime timeline for a highlight titled "rt-claude test highlight". If it says no API key was found, tell me how to set one. If it returns an HTTP error (e.g. 400), explain the likely cause (usually a bad or missing key).
