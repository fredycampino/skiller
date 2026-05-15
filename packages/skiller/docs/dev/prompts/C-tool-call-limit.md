# C. Tool Call Limit

Purpose: verify that `agent.loop.max_tool_calls` rejects one assistant response
that contains too many tool calls.

Prompt:

```text
Use the shell tool to run 6 separate commands.

1. `pwd`
2. `git branch --show-current`
3. `git status --porcelain`
4. `python --version`
5. `ls packages`
6. `ls packages/skiller`

Important:

- Emit all 6 shell tool calls in your next assistant response.
- Do not wait for any tool result before emitting the 6 tool calls.
- Do not combine commands.
- Each item must be a separate tool call.
```

Expected behavior:

- If the configured `max_tool_calls` is lower than 6, Skiller rejects the whole
  batch before executing any tool.
- Agent context receives one corrective `user_message`.
- No `assistant_message`, `tool_call`, or `tool_result` is appended for the
  rejected batch.

Notes:

- The default fallback is `agent.loop.max_tool_calls = 5`, so 6 calls should
  exceed the default limit.
- This is a prompt-based manual test. It only validates the limit if the LLM
  emits the 6 tool calls in one assistant response.
