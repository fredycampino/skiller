# Agent Loop

This page defines the decision contract for the internal `agent` loop.

## Status

Current behavior.

Current implementation status:

- native `tool_calls` are the only supported tool contract
- native `content + tool_calls` turns are preserved in `agent context`
- multi-tool turns are implemented
- terminal agent states without assistant text emit dedicated runtime events
- streaming assembly is still open

## Goal

Describe how the agent runner reacts to assistant content, native tool calls,
tool preparation results, interrupts, and loop limits.

The loop must stay deterministic and easy to reason about:

- one turn produces one assistant decision
- the runner advances one turn per assistant response, not per tool call
- one assistant turn can execute more than one tool call
- agent-correctable tool failures are visible to the LLM on the next turn
- technical tool preparation failures terminate the agent step

## Agent Turn Flow

| LLM response | action | agent context effect | next state |
| --- | --- | --- | --- |
| `content`, no tools | accept as final answer | append `assistant_message` with `message_type = "final"` | finish `final` |
| tool-only response | execute the tool batch | append one `tool_call` / `tool_result` pair per executed tool | next agent turn |
| `content + tool_calls` | persist the assistant content, then execute the tool batch | append `assistant_message` with `message_type = "tool_calls"`; child tool entries use its `parent_sequence` | next agent turn |
| LLM request failure | stop the runner | no final assistant message | step raises; runtime records run failure |

## Tool Batch Flow

| case | action | agent context effect | next state |
| --- | --- | --- | --- |
| valid tool call | append `tool_call`, prepare tool, execute tool | append `tool_result` when execution returns a `ToolResult` | continue batch |
| invalid tool-call JSON | append corrective feedback for the agent | append one corrective `user_message`; no `tool_call` is appended for that invalid call | continue batch |
| more than `loop.max_tool_calls` | reject the whole batch before executing any tool | append one corrective `user_message`; append no `tool_call` or `tool_result` for the batch | next agent turn |
| user interrupt before a tool starts | stop the current tool batch | append one control `user_message`; already executed tools stay persisted | finish `interrupted` |
| process tool interruption while waiting | terminate the process and stop the current tool batch | append one control `user_message`; no `tool_result` for the interrupted tool | finish `interrupted` |
| batch completes | return control to the agent runner | no extra end marker is persisted | next agent turn |

## Tool Prepare Outcomes

`ToolManager.prepare()` resolves the tool, converts raw args into the typed tool
request, and applies policy.

| prepare outcome | meaning | agent context effect | next state |
| --- | --- | --- | --- |
| `ok` | tool is ready to execute | execution appends the normal `tool_result` | continue batch |
| `request_invalid` | the LLM or step used the tool incorrectly, or the tool is unknown/disallowed | append failed `tool_result` with `data.error = "request_invalid"` | continue batch |
| `policy_blocked` | the tool policy rejected the request | append failed `tool_result` with `data.error = "policy_blocked"` | continue batch |
| `request_exception` | `tool.request()` raised unexpectedly | append the `tool_call` only; no corrective feedback and no `tool_result` | finish `tool_execution_failed`; step raises |
| `policy_exception` | `tool.policy()` raised unexpectedly | append the `tool_call` only; no corrective feedback and no `tool_result` | finish `tool_execution_failed`; step raises |

## Terminal Outcomes

The agent loop has three non-error terminal shapes:

| finish | runtime event | assistant message | step output |
| --- | --- | --- | --- |
| `final` | `AGENT_FINAL_ASSISTANT_MESSAGE` | yes | `data.stop_reason = "final"` and `data.final` contains the final text |
| `interrupted` | `AGENT_INTERRUPTED` | no | `data.stop_reason = "interrupted"` and `data.message` contains the stop explanation |
| `max_turns_exhausted` | `AGENT_MAX_TURNS_EXHAUSTED` | no | `data.stop_reason = "max_turns_exhausted"` and `data.message` contains the stop explanation |
| `config_invalid` | none | no | `data.stop_reason = "config_invalid"` and `data.message` contains the validation error |

Technical failures:

- `invalid_final_message`
  - Cause: the LLM returned an empty final answer when a final answer was required.
  - Context effect: no final assistant message.
  - Runtime effect: agent step raises; runtime records step/run failure.
- `llm_request_failed`
  - Cause: LLM port returned `ok = false`.
  - Context effect: no final assistant message.
  - Runtime effect: agent step records normal output with
    `data.stop_reason = "llm_request_failed"` and follows `next`.
- `tool_execution_failed`
  - Cause: tool preparation returned `request_exception` or `policy_exception`.
  - Context effect: no final assistant message.
  - Runtime effect: agent step raises; runtime records step/run failure.

Consumers must not infer interrupt or max-turn states from an empty assistant
message. Those states are explicit runtime events and explicit step output stop
reasons.

## Limit Cases

| limit case | action | agent context effect | next state |
| --- | --- | --- | --- |
| within `loop.max_tool_calls` | accept the batch | append entries according to the tool batch shape | continue batch, then next agent turn |
| exceeds `loop.max_tool_calls` | reject the batch before any tool execution | append one corrective `user_message` | next agent turn |
| within `loop.max_turns` | continue normal agent turns | append entries produced by each turn | continue |
| last remaining turn with tools enabled | append last-turn warning before the LLM request | append one control `user_message` once per agent scope | continue |
| exhausts `loop.max_turns` without final answer | stop without creating a final assistant message | append one control `user_message`; emit `AGENT_MAX_TURNS_EXHAUSTED` | finish `max_turns_exhausted` |
| interrupt before `max_turns` is exhausted | stop because of steering, not numeric budget | append one control `user_message`; emit `AGENT_INTERRUPTED` | finish `interrupted` |

## Notes

- `parent_sequence` exists only when the same assistant turn appended
  `assistant_message` content.
- Invalid tool-call JSON does not cancel other valid tool calls in the same
  response.
- `request_invalid` and `policy_blocked` are agent-correctable and are persisted
  as failed `tool_result` entries.
- `llm_request_failed` is recoverable by the flow through the agent step output
  and `next`.
- `request_exception`, `policy_exception`, and invalid final messages are
  technical failures and terminate the agent step.
- Interrupt is consumed inside the tool loop, not before the LLM call.
- Interrupt and max-turn exhaustion do not persist final `assistant_message`
  entries.
- Legacy JSON tool decisions are no longer part of the contract.
- Streaming is out of scope for the current `LLMPort` contract.

## Related Docs

- [`./agent-tools.md`](./agent-tools.md)
- [`./agent-context.md`](./agent-context.md)
- [`./agent-flow.md`](./agent-flow.md)
- [`../runtime/agent-architecture.md`](../runtime/agent-architecture.md)
