# Agent Context

## Status

Implemented.

## Goal

Persist agent memory as append-only entries.

`runs.step_executions_json` stores one observable output per `step_id`. It is not suitable for
agent memory because one `agent` step can produce multiple turns under the same `step_id`.

## Logical Model

```python
AgentContextEntry(
    id: str,
    run_id: str,
    context_id: str,
    sequence: int,
    entry_type: str,
    message_type: str | None,
    window_tokens: int | None,
    window_start_sequence: int | None,
    payload: AgentContextPayload,
    usage: LLMUsage | None,
    source_step_id: str,
    created_at: str,
)
```

Fields:

- `id`: unique entry id.
- `run_id`: run that owns this context entry.
- `context_id`: logical agent memory id inside the run.
- `sequence`: monotonic order within `context_id`.
- `entry_type`: one of the supported entry types.
- `message_type`: assistant message subtype, when the entry is an assistant message.
- `window_tokens`: tokens reported by the LLM for the context window used by that request.
- `window_start_sequence`: first entry sequence of the context window used by that request.
- `payload`: typed entry content used to rebuild the agent prompt. It is persisted as JSON.
- `usage`: optional LLM token usage. Currently present on assistant response entries.
- `source_step_id`: `agent` step that created the entry.
- `created_at`: entry creation timestamp.

Entry types:

- `user_message`
- `assistant_message`
- `tool_call`
- `tool_result`

Payload model:

```python
AgentContextPayload =
  AgentUserMessagePayload
  | AgentAssistantMessagePayload
  | AgentToolCallPayload
  | AgentToolResultPayload
```

## Table

```text
+-----------------------+---------+--------------------------------------+
| column                | type    | notes                                |
+-----------------------+---------+--------------------------------------+
| id                    | TEXT    | PK                                   |
| run_id                | TEXT    | NOT NULL, FK -> runs(id)             |
| context_id            | TEXT    | NOT NULL                             |
| sequence              | INTEGER | NOT NULL                             |
| entry_type            | TEXT    | NOT NULL                             |
| message_type          | TEXT    | NULL, assistant message subtype      |
| window_tokens         | INTEGER | NULL, assistant final window tokens  |
| window_start_sequence | INTEGER | NULL, window start for token reading |
| payload_json          | TEXT    | NOT NULL, full payload               |
| usage_json            | TEXT    | NULL, LLM usage for response entries |
| source_step_id        | TEXT    | NOT NULL                             |
| created_at            | TEXT    | NOT NULL, default CURRENT_TIMESTAMP  |
+-----------------------+---------+--------------------------------------+
```

Indexes:

```text
idx_agent_context_entries_context(context_id, sequence)
idx_agent_context_entries_final_marker(context_id, entry_type, message_type, window_tokens, sequence)
```

`message_type`, `window_tokens`, and `window_start_sequence` duplicate assistant metadata on
purpose. They make context-window queries cheap without parsing `payload_json` or `usage_json`.

## Entry Payloads

User message:

```json
{
  "type": "user_message",
  "text": "Check the latest build failure."
}
```

Assistant final message:

```json
{
  "type": "assistant_message",
  "turn_id": "turn-2",
  "message_type": "final",
  "text": "The failing test is test_example.py::test_build."
}
```

Assistant message that introduces tool calls:

```json
{
  "type": "assistant_message",
  "turn_id": "turn-1",
  "message_type": "tool_calls",
  "text": "I will inspect the failing command output before answering."
}
```

Assistant payload is prompt content. Token-window metadata lives in indexed entry columns and
`usage_json`; it must not be sent back to the LLM as prompt content.

Tool call:

```json
{
  "type": "tool_call",
  "turn_id": "turn-1",
  "parent_sequence": 2,
  "tool_call_id": "call-1",
  "tool": "shell",
  "args": {
    "command": "pytest -q"
  }
}
```

Tool result:

```json
{
  "type": "tool_result",
  "turn_id": "turn-1",
  "parent_sequence": 2,
  "tool_call_id": "call-1",
  "tool": "shell",
  "status": "COMPLETED",
  "data": {
    "ok": false,
    "exit_code": 1,
    "stderr": "..."
  },
  "text": "",
  "error": null
}
```

## Example Context

An `agent` loop reconstructs `AgentContext` from ordered entries:

```json
{
  "run_id": "run-1",
  "context_id": "thread-1",
  "entries": [
    {
      "id": "entry-1",
      "sequence": 1,
      "entry_type": "user_message",
      "payload": {
        "type": "user_message",
        "text": "Check why the tests are failing."
      },
      "source_step_id": "support_agent",
      "created_at": "2026-04-22T21:40:00Z"
    },
    {
      "id": "entry-2",
      "sequence": 2,
      "entry_type": "assistant_message",
      "message_type": "tool_calls",
      "window_tokens": null,
      "window_start_sequence": null,
      "payload": {
        "type": "assistant_message",
        "turn_id": "turn-1",
        "message_type": "tool_calls",
        "text": "I will inspect the test output before answering."
      },
      "usage": {
        "prompt_tokens": 80,
        "completion_tokens": 16,
        "total_tokens": 96,
        "provider": "minimax",
        "model": "MiniMax-M2.5"
      },
      "source_step_id": "support_agent",
      "created_at": "2026-04-22T21:40:03Z"
    },
    {
      "id": "entry-3",
      "sequence": 3,
      "entry_type": "tool_call",
      "payload": {
        "type": "tool_call",
        "turn_id": "turn-1",
        "parent_sequence": 2,
        "tool_call_id": "call-1",
        "tool": "shell",
        "args": {
          "command": "pytest -q"
        }
      },
      "source_step_id": "support_agent",
      "created_at": "2026-04-22T21:40:05Z"
    },
    {
      "id": "entry-4",
      "sequence": 4,
      "entry_type": "tool_result",
      "payload": {
        "type": "tool_result",
        "turn_id": "turn-1",
        "parent_sequence": 2,
        "tool_call_id": "call-1",
        "tool": "shell",
        "status": "COMPLETED",
        "data": {
          "ok": false,
          "exit_code": 1,
          "stderr": "ModuleNotFoundError: No module named 'requests'"
        },
        "text": "",
        "error": null
      },
      "source_step_id": "support_agent",
      "created_at": "2026-04-22T21:40:08Z"
    },
    {
      "id": "entry-5",
      "sequence": 5,
      "entry_type": "assistant_message",
      "message_type": "final",
      "window_tokens": 79,
      "window_start_sequence": 1,
      "payload": {
        "type": "assistant_message",
        "turn_id": "turn-2",
        "message_type": "final",
        "text": "The tests fail because `requests` is missing."
      },
      "usage": {
        "prompt_tokens": 63,
        "completion_tokens": 16,
        "total_tokens": 79,
        "provider": "minimax",
        "model": "MiniMax-M2.5"
      },
      "source_step_id": "support_agent",
      "created_at": "2026-04-22T21:40:15Z"
    }
  ]
}
```

This example has one user task, one tool call inside `turn-1`, and one final assistant turn.

`turn_id` groups entries that belong to the same assistant response.
`tool_call_id` identifies one concrete tool call inside that turn.
`message_type` distinguishes assistant content that introduces tool calls from final assistant content.
`parent_sequence` links `tool_call` and `tool_result` entries back to the assistant message of the same turn.

That allows one assistant turn to persist:

- one assistant content block
- multiple `tool_call` entries
- multiple `tool_result` entries

## Multi-Tool Turns

The current context model supports more than one tool call in the same assistant turn.

The persistence shape is:

- one shared `turn_id` for the whole assistant turn
- one distinct `tool_call_id` per native tool call
- one `tool_result` matched to the same `tool_call_id`

Prompt reconstruction uses:

- `assistant(..., tool_calls=[...])` for all tool calls of the turn
- one `tool(...)` message per persisted tool result

This keeps the next LLM request aligned with the original provider response order.

## Read Model

Load context entries by `context_id`, ordered by `sequence`.

For full prompt construction:

```sql
SELECT *
FROM agent_context_entries
WHERE context_id = ?
ORDER BY sequence ASC
```

For normal agent execution, the runner uses a sliding context window instead of loading the
full context.

## Context Window

The window is a read limit, not summarization or compaction.

Inputs:

- `providers.<name>.context_window_tokens`: provider context capacity.
- `context.compaction.max_total_tokens_ratio`: fraction of the provider capacity used
  for context reads.

Resolved request metadata:

```python
AgentContextLLMRequest(
    context_id: str,
    turn_id: str,
    llm_request: LLMRequest,
    context_window_tokens: int,
    window_start_sequence: int,
    window_end_sequence: int,
    max_ratio: float,
    estimated_tokens: int,
)
```

Fields:

- `context_id`: context being read.
- `turn_id`: next agent turn id.
- `llm_request`: provider-ready request built from system prompt, window entries, and tools.
- `context_window_tokens`: resolved token limit used for the context-window query.
- `window_start_sequence`: first selected entry sequence in the context window, or `0`
  when the window is empty.
- `window_end_sequence`: last selected entry sequence in the context window, or `0`
  when the window is empty.
- `max_ratio`: configured ratio used to calculate `context_window_tokens`.
- `estimated_tokens`: estimated token size of the selected window. It is `0` when the selected
  entries do not expose usable assistant final totals.

Window selection example:

```text
context_window_tokens = 80000

latest final:
  sequence = 40
  window_tokens = 100000
  window_start_sequence = 1

cutoff = 100000 - 80000 = 20000

first final inside the current window with window_tokens > 20000:
  sequence = 12

next window:
  entries where sequence >= 12
  start_sequence = 12
  end_sequence = latest selected entry sequence
```

If the latest final is already under the limit, the next window starts at the
latest final's persisted `window_start_sequence`. If there is no final marker yet,
the next window uses all entries.

The selected window is returned as:

```python
AgentContextWindow(
    entries: list[AgentContextEntry],
    start_sequence: int,
    end_sequence: int,
)
```

`start_sequence` is the value propagated to the final assistant entry as
`window_start_sequence`. No later layer recalculates it.

The window start only moves forward. Once a context has crossed the window limit, later requests
must not return to sequence `0` just because the latest reported `window_tokens` falls below the
limit.

Final assistant entries persist the reference used to produce their token reading:

```json
{
  "sequence": 412,
  "entry_type": "assistant_message",
  "message_type": "final",
  "window_tokens": 73835,
  "window_start_sequence": 274
}
```

This means `73835` tokens were measured from entry `274`, not from the full historical context.

Window token estimate:

```text
estimated_tokens = last_selected_entry.window_tokens - first_selected_entry.window_tokens
```

The estimate only reads the first and last selected entries. If the first selected entry is not a
final assistant message, the estimate falls back to the last selected entry total. If the last
selected entry is not a final assistant message, the estimate is `0`.

## Relationship To Existing Tables

- `runs.step_executions_json` stores the final observable output of the `agent` step.
- `agent_context_entries` stores the internal append-only memory used by the agent loop.
- `agent_context_entries.payload_json` is the source of truth for each memory entry and may be
  large.
- `agent_context_entries.usage_json` stores token usage plus provider/model metadata
  for assistant response entries. Context usage stats expose the latest final assistant usage.
- `agent_context_entries.message_type`, `agent_context_entries.window_tokens`, and
  `agent_context_entries.window_start_sequence` are indexed assistant metadata for
  context-window reads.
- `events` remains an observability stream, not the functional source of truth.
