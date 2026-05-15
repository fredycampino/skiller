# E. Max Turns

Purpose: verify that `agent.loop.max_turns` stops an agent step that keeps
requesting more tool turns without producing a final answer.

This test is different from `C-tool-call-limit.md`: it does not validate
`agent.loop.max_tool_calls`. It validates that the agent runner stops after the
configured number of assistant turns.

Prompt:

```text
Use the shell tool to inspect the repository in many small steps.

Important rules:

- Run exactly one shell command per assistant turn.
- After each tool result, continue with the next numbered command.
- Do not combine commands.
- Do not provide a final answer until all 15 commands have been executed.

Commands:

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
15. `ls packages/skiller/docs/dev/prompts`
```

Expected behavior:

- The agent executes at most one shell tool call per assistant turn.
- If `agent.loop.max_turns` is lower than the number of turns needed to finish,
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
