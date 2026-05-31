# E. Max Turns

Purpose: verify that `loop.max_turns` stops an agent step that keeps
requesting more tool turns without producing a final answer.

This test is different from `C-tool-call-limit.md`: it does not validate
`loop.max_tool_calls`. It validates that the agent runner stops after the
configured number of assistant turns.

Prompt:

```text
Use the shell tool to inspect the repository in many small steps.

Before running commands, determine the configured `loop.max_turns` / agent
`max_turns` for the agent being tested. If that value is not provided in the
prompt or visible in the current agent configuration, ask the user:

`What is this agent's max_turns value, or how many shell-tool turns should this test use?`

Once the value is known, run more shell-tool turns than that limit. For example,
if `max_turns` is 20, run at least 21 shell commands.

Important rules:

- Run exactly one shell command per assistant turn.
- After each tool result, continue with the next numbered command.
- Do not combine commands.
- Do not ask for confirmation between commands once the turn count is known.
- Do not provide a final answer until all requested commands have been executed
  or the runtime stops the agent because max turns were exhausted.

Command plan:

Use the following commands in order, cycling back to command 1 if more turns are
needed than this list contains:

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
12. `ls apps`
13. `ls apps/tui`
14. `ls packages/skiller/agents`
15. `ls packages/skiller/docs/dev`
```

Expected behavior:

- The agent executes at most one shell tool call per assistant turn.
- If `loop.max_turns` is lower than the number of turns needed to finish,
  the agent runner stops before the final answer.
- Agent context receives one max-turns control `user_message`.
- Runtime emits `AGENT_MAX_TURNS_EXHAUSTED`.
- The agent step finishes with `stop_reason = "max_turns_exhausted"` and no
  final `assistant_message` is persisted for that stop condition.

Notes:

- This is a prompt-based manual test and depends on the LLM following the
  one-command-per-turn instruction.
- If the LLM emits multiple tool calls in one assistant response, the test no
  longer isolates `max_turns`.
