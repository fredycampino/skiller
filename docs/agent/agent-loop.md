# Agent Loop

This page defines the decision contract for the internal `agent` loop.

## Status

Current behavior.

Current implementation status:

- native `tool_calls` are the only supported tool contract
- native `content + tool_calls` turns are preserved in `agent context`
- multi-tool turns are implemented
- streaming assembly is still open

## Goal

Describe the behavior of the current agent loop when the assistant returns content,
tool calls, or invalid tool payloads.

The loop must stay deterministic and easy to reason about:

- one turn produces one assistant decision
- every tool execution is persisted in `agent context`
- every tool failure is visible to the LLM on the next turn
- one assistant turn can execute more than one tool call

## Cases

| case | result / error | agent context effect | status agent |
| --- | --- | --- | --- |
| 1. `content` normal, no tools | accept as final answer | append one assistant message with the final text | finalizes successfully |
| 2. tool-only response with one valid `tool_call` | execute the tool, append `tool_call` and `tool_result`, then continue | append one `tool_call` and one `tool_result`; no `assistant_message` parent exists for that turn | continues |
| 3. tool-only response with multiple valid `tool_calls` | execute them one by one, in order of appearance | append one `tool_call` / `tool_result` pair per valid tool call | continues |
| 4. `content` + one valid `tool_call` | keep the content and execute the tool call | append one `assistant_message` with `message_type = "tool_calls"`, then append `tool_call` and `tool_result` with `parent_sequence` pointing to that assistant message | continues |
| 5. `content` + multiple valid `tool_calls` | keep the content and execute the tool calls in order | append one `assistant_message` with `message_type = "tool_calls"`, then append one `tool_call` / `tool_result` pair per valid tool call; all children share the same `parent_sequence` | continues |
| 6. `tool_call` with invalid arguments | persist validation feedback and continue with the remaining tool calls of the same assistant turn | append one corrective `user_message`; valid tool calls in the same turn still execute | continues |
| 7. `tool_call` to an unknown or disallowed tool | persist an explicit tool failure, do not execute the external tool successfully | append a failed `tool_result` with the error text | continues |
| 8. more than `agent.loop.max_tool_calls` in one response | reject the whole batch and return corrective feedback to the LLM | append one `user_message` explaining the limit; append no `tool_call` or `tool_result` entries for that batch | continues |
| 9. user interrupts the current agent turn during the tool loop | stop executing remaining tool calls in the batch and return a short final assistant message | append one control `user_message`; already executed tools stay persisted; then append one final `assistant_message` | finalizes the agent step, then follows `next` |
| 10. tool block completes for the current assistant turn | finish the current tool block and return control to the agent loop | no extra end marker is persisted in `agent context`; the loop simply stops appending tool entries for that turn | continues |
| 11. tool call parsing fails for every tool in the assistant response | do not execute any tools; re-prompt the LLM on the next turn with corrective feedback | append one corrective `user_message` per invalid tool call; append no `tool_result` entries for that turn | continues |
| 12. streaming with fragmented `tool_calls` | buffer fragments until the tool call is complete; if the stream ends incomplete, report an error to the LLM | persist only complete tool calls and complete tool results | not supported |

## Limit Cases

| limit case | result / error | agent context effect | status agent |
| --- | --- | --- | --- |
| 1. assistant response stays within `agent.loop.max_tool_calls` | accept the tool batch and execute valid tool calls in order | normal `assistant_message`, `tool_call`, and `tool_result` entries are appended according to the turn shape | continues in the current tool batch, then continues to the next agent turn |
| 2. assistant response exceeds `agent.loop.max_tool_calls` | reject the whole tool batch before any tool execution | append one corrective `user_message`; append no `tool_call` and no `tool_result` entries for that batch | consumes one agent turn, then continues to the next agent turn |
| 3. agent loop stays within `agent.loop.max_turns` | accept the final answer before the turn budget is exhausted | append the entries produced by each turn, then append the final `assistant_message` | finalizes successfully |
| 4. agent loop exhausts `agent.loop.max_turns` without a final answer | stop the agent loop without failing the run and return a short final assistant message | append one control `user_message` asking whether to continue; the already persisted context stays as-is; then append one final `assistant_message` | finalizes the agent step, then follows `next` |
| 5. interrupt happens before `agent.loop.max_turns` is exhausted | stop early because of steering, not because a numeric limit was reached | append one control `user_message`; keep already persisted tool entries; then append one final `assistant_message` | finalizes the agent step, then follows `next` |


## Notes

- The loop supports more than one native `tool_call` per response.
- The runner advances one turn per assistant response, not per tool call.
- Validation feedback for an invalid tool call does not cancel other valid tool calls in the same response.
- The runtime enforces `agent.loop.max_tool_calls` before executing a tool batch.
- When only one turn remains and tools are enabled, the prompt adds a last-turn warning that asks the model to either finish now or ask the user whether to continue.
- An interrupt is consumed inside the tool loop, not before the LLM call.
- `parent_sequence` exists only when the same assistant turn appended `assistant_message` content.
- Legacy JSON tool decisions are no longer part of the contract.
- Streaming is out of scope for the current `LLMPort` contract.

## Related Docs

- [`./agent-tools.md`](./agent-tools.md)
- [`./agent-context.md`](./agent-context.md)
- [`./agent-flow.md`](./agent-flow.md)
- [`../runtime/agent-architecture.md`](../runtime/agent-architecture.md)
