# B. Multiple Shell Calls

Purpose: verify that the agent can execute several valid shell tool calls in one
or more turns.

Prompt:

```text
Use the shell tool to run these checks one by one:

1. `pwd`
2. `git branch --show-current`
3. `git status --porcelain`
4. `python --version`
5. `ls packages/skiller/docs/agent`

Then summarize the results in a short list.
```

Expected behavior:

- Valid shell calls execute in order.
- Each executed tool call appends a `tool_call` and a `tool_result`.
- The agent returns a final summary.
