# C. Tool Call Limit

Purpose: verify that `agent.loop.max_tool_calls` rejects a batch that contains
too many tool calls.

Prompt:

```text
Use the shell tool to run 11 separate commands:

1. `pwd`
2. `git branch --show-current`
3. `git status --porcelain`
4. `python --version`
5. `ls packages`
6. `ls packages/skiller`
7. `ls packages/skiller/docs`
8. `ls packages/skiller/src`
9. `ls packages/skiller/tests`
10. `git log --oneline -1`
11. `git diff --stat`

Do not combine commands. Each item must be a separate tool call.
```

Expected behavior:

- If the configured `max_tool_calls` is lower than 11, Skiller rejects the whole
  batch before executing any tool.
- Agent context receives one corrective `user_message`.
- No `tool_call` or `tool_result` is appended for the rejected batch.
